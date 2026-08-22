"""N2: rediscovery of tau2 hand-authored tasks by schema-only generation.

The generator consumes ONLY the exported domain schemas (results/repro/schema).
Matching against their tasks happens here - after generation - using the
frozen D9 definition: STRICT = exact action-name + complete-argument equality
over the whole sequence, hashed for scale. A secondary WRITES-ONLY view
(mutating actions' names + entity-id bindings) is reported alongside.

Usage: python scripts/run_n2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))

from oosc.adapters.corruptions import is_write  # noqa: E402
from oosc.generate.engine import ScenarioGenerator, actions_digest  # noqa: E402
from oosc.schema import DomainDef  # noqa: E402

SCHEMA_DIR = REPO / "results" / "repro" / "schema"
OUT_DIR = REPO / "results" / "n2"


def writes_digest(actions: list[dict]) -> str:
    w = [
        (a["name"], {k: v for k, v in a["arguments"].items() if k.endswith(("_id", "_ids"))})
        for a in actions
        if is_write(a["name"])
    ]
    return actions_digest([(n, a) for n, a in w])


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {}
    for domain in ["retail", "airline"]:
        dom = DomainDef.model_validate(json.load(open(SCHEMA_DIR / f"{domain}.domain.json", encoding="utf-8")))
        sigs = ScenarioGenerator(dom).enumerate_signatures()
        their_tasks = json.load(open(SCHEMA_DIR / f"{domain}.tasks.json", encoding="utf-8"))
        n_strict = n_writes = 0
        misses = []
        for t in their_tasks:
            acts = t["criteria"]["actions"]
            if not acts:
                continue
            hit_s = actions_digest([(a["name"], a["arguments"]) for a in acts]) in sigs["strict"]
            hit_w = len(acts) > 0 and writes_digest(acts) in sigs["writes"]
            n_strict += int(hit_s)
            n_writes += int(hit_w)
            if not hit_s:
                misses.append({"task": t["id"], "writes_hit": hit_w, "n_actions": len(acts)})
        report[domain] = {
            "tasks": len(their_tasks),
            "generated_strict_signatures": len(sigs["strict"]),
            "strict_hits": n_strict,
            "writes_only_hits": n_writes,
            "strict_rate": round(n_strict / len(their_tasks), 4),
            "writes_only_rate": round(n_writes / len(their_tasks), 4),
            "misses_sample": misses[:25],
        }
        print(f"[{domain}] digests={len(sigs['strict'])} strict={n_strict}/{len(their_tasks)} writes={n_writes}/{len(their_tasks)}")
    total_tasks = sum(r["tasks"] for r in report.values())
    total_strict = sum(r["strict_hits"] for r in report.values())
    total_writes = sum(r["writes_only_hits"] for r in report.values())
    report["_overall"] = {
        "tasks": total_tasks,
        "strict": f"{total_strict}/{total_tasks}",
        "strict_rate": round(total_strict / total_tasks, 4),
        "writes_only": f"{total_writes}/{total_tasks}",
        "writes_only_rate": round(total_writes / total_tasks, 4),
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report["_overall"], indent=1))
    print(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
