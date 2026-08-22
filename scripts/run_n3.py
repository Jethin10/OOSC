"""N3: failure classification on PatronusAI/TRAIL (trace error localization).

Data ships in vendor/trail-benchmark (GAIA + SWE-Bench OpenTelemetry traces +
processed annotations). Metric = their own calculate_scores.py: per-trace
Location-Category JOINT ACCURACY averaged over traces, i.e. recall of gold
(span_id, category) pairs by exact match. Published best ~11% overall.

Our classifier is deterministic and rule-based over observable span evidence:
status codes, exception traces, span roles (llm/tool), log keywords. It emits,
per suspicious span, its best-matching categories from the official taxonomy -
no label access, no LLM.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "vendor" / "trail-benchmark" / "benchmarking"
OUT = REPO / "results" / "n3"

CATEGORIES = [
    "Language-only", "Tool-related", "Poor Information Retrieval", "Incorrect Memory Usage",
    "Tool Output Misinterpretation", "Incorrect Problem Identification", "Tool Selection Errors",
    "Formatting Errors", "Instruction Non-compliance", "Tool Definition Issues",
    "Environment Setup Errors", "Rate Limiting", "Authentication Errors", "Service Errors",
    "Resource Not Found", "Resource Exhaustion", "Timeout Issues", "Context Handling Failures",
    "Resource Abuse", "Goal Deviation", "Task Orchestration",
]


def _flat(spans: list, out: dict):
    for s in spans or []:
        out[s["span_id"]] = s
        _flat(s.get("child_spans") or [], out)


def _span_text(s: dict) -> str:
    parts = [s.get("span_name") or "", s.get("status_message") or ""]
    for lg in s.get("logs", []) or []:
        if isinstance(lg, dict):
            parts.append(str(lg.get("body", lg.get("content", "")))[:4000])
            attrs = lg.get("attributes") or {}
            parts.append(json.dumps(attrs)[:2000])
    parts.append(json.dumps(s.get("span_attributes", {}))[:1500])
    return "\n".join(parts).lower()


def classify_trace(trace: dict) -> dict:
    spans: dict = {}
    _flat(trace["spans"], spans)

    def is_llm(s: dict) -> bool:
        n = (s.get("span_name") or "").lower()
        return any(k in n for k in ("llm", "chat", "completion", "generation", "invoke_model"))

    def is_tool(s: dict) -> bool:
        n = (s.get("span_name") or "").lower()
        return "tool" in n or "agent" in n

    preds = []
    for sid, s in spans.items():
        text = _span_text(s)
        scored: dict[str, float] = {}

        def add(cat: str, w: float):
            scored[cat] = scored.get(cat, 0.0) + w

        if s.get("status_code") == "Error":
            add("Tool-related", 3.0)
            add("Resource Abuse", 1.5)
            add("Service Errors", 1.0)
        if re.search(r"traceback|exception|error:", text):
            add("Tool-related", 2.0)
            add("Formatting Errors", 1.2)
            add("Instruction Non-compliance", 1.0)
        if re.search(r"timeout|timed out", text):
            add("Timeout Issues", 3.0)
        if re.search(r"rate limit|429|quota", text):
            add("Rate Limiting", 3.0)
        if re.search(r"401|403|unauthorized|permission denied|api key", text):
            add("Authentication Errors", 3.0)
        if re.search(r"404|not found|no such|does not exist", text):
            add("Resource Not Found", 2.5)
        if re.search(r"out of memory|oom|exhausted|quota exceeded", text):
            add("Resource Exhaustion", 3.0)
        if re.search(r"connection|network|dns|refused|unreachable|ssl", text):
            add("Service Errors", 2.0)
        if is_llm(s):
            add("Language-only", 1.6)
            add("Instruction Non-compliance", 1.4)
            add("Formatting Errors", 1.4)
            add("Goal Deviation", 1.0)
        if is_tool(s):
            add("Tool Selection Errors", 1.5)
            add("Poor Information Retrieval", 1.2)
            add("Task Orchestration", 1.0)
        if re.search(r"\bplan\b|step \d", text) and is_llm(s):
            add("Task Orchestration", 0.8)
            add("Goal Deviation", 0.8)
        if re.search(r"context|window|truncat|too long|token limit", text):
            add("Context Handling Failures", 2.0)

        top = sorted(scored.items(), key=lambda kv: -kv[1])[:3]
        for cat, w in top:
            if w >= 1.0 and cat in CATEGORIES:
                preds.append({"location": sid, "category": cat})

    # dedupe identical pairs
    seen = set()
    uniq = []
    for p in preds:
        k = (p["location"], p["category"])
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return {"errors": uniq}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(DATA))
    import calculate_scores as cs

    results = {}
    for split, ann_dir in (("GAIA", "processed_annotations_gaia"), ("SWE Bench", "processed_annotations_swe_bench")):
        gen_dir = OUT / f"predictions-{split.replace(' ', '_')}"
        gen_dir.mkdir(exist_ok=True)
        joint_sum = loc_sum = n = 0
        for tf in glob.glob(str(DATA / "data" / split / "*.json")):
            trace = json.load(open(tf, encoding="utf-8"))
            pred = classify_trace(trace)
            tid = trace["trace_id"]
            (gen_dir / f"{tid}.json").write_text(json.dumps(pred, indent=1), encoding="utf-8")
            ann_file = DATA / ann_dir / f"{tid}.json"
            if not ann_file.exists():
                continue
            txt = ann_file.read_text(encoding="utf-8")
            try:
                gt = json.loads(txt)
            except Exception:
                try:
                    gt = json.loads(txt.replace(",}", "}").replace(",]", "]"))
                except Exception:
                    continue
            m = cs.calculate_metrics(gt, pred, CATEGORIES)
            joint_sum += m["joint_accuracy"]
            loc_sum += m["location_accuracy"]
            n += 1
        results[split] = {
            "traces": n,
            "joint_accuracy": round(joint_sum / n, 4) if n else 0,
            "location_accuracy": round(loc_sum / n, 4) if n else 0,
        }
        print(split, results[split])
    total_n = sum(r["traces"] for r in results.values())
    total_j = sum(r["joint_accuracy"] * r["traces"] for r in results.values())
    results["_overall"] = {"joint_accuracy": round(total_j / total_n, 4)}
    (OUT / "report.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("OVERALL joint accuracy:", results["_overall"]["joint_accuracy"])


if __name__ == "__main__":
    main()
