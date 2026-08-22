"""N1: oracle agreement vs tau2-bench gold rewards across their 164 tasks.

For every retail + airline task we grade a set of trajectory variants with BOTH
oracles - ours (schema-derived world) and theirs (real domain code) - and
measure binary-verdict agreement. Variants come from the frozen taxonomy in
corruptions.py; the RNG is seeded per (domain, task, variant) so runs are
reproducible.

Split discipline: 20% of tasks (stable hash of task id) form a HOLDOUT that is
never looked at during model iteration; final numbers are reported on both
dev and holdout.

Usage: python scripts/run_n1.py [--out results/n1]
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))

from oosc.adapters.corruptions import Variant, corrupt, load_param_hints  # noqa: E402
from oosc.adapters.tau2_gold import gold_reward, make_task_lookup  # noqa: E402
from oosc.oracle import Oracle  # noqa: E402
from oosc.schema import DomainDef, TaskCriteria  # noqa: E402

DOMAINS = ["retail", "airline"]
SCHEMA_DIR = REPO / "results" / "repro" / "schema"


def holdout(task_id: str) -> bool:
    h = int(hashlib.sha1(f"oosc-holdout:{task_id}".encode()).hexdigest(), 16)
    return h % 5 == 0


def run(domain: str, out_dir: Path) -> dict:
    dom = DomainDef.model_validate(json.load(open(SCHEMA_DIR / f"{domain}.domain.json", encoding="utf-8")))
    load_param_hints(dom)
    norm_tasks = json.load(open(SCHEMA_DIR / f"{domain}.tasks.json", encoding="utf-8"))
    tau2_tasks = make_task_lookup(domain)
    oracle = Oracle(dom)

    rows = []
    for nt in norm_tasks:
        tid = nt["id"]
        task = tau2_tasks[tid]
        crit = TaskCriteria(
            actions=nt["criteria"]["actions"],
            communicate_info=[c for c in nt["criteria"]["communicate_info"]],
            reward_basis=[b for b in nt["criteria"]["reward_basis"] if b != "NL_ASSERTION"],
        )
        if not crit.reward_basis:
            crit.reward_basis = ["DB"]
        for variant in Variant:
            rng = random.Random(f"{domain}:{tid}:{variant.value}")
            steps = corrupt(variant, crit.actions, crit.communicate_info, dom, rng)
            ours = oracle.grade(crit, steps)
            theirs = gold_reward(task, steps, domain)
            agree = (ours.reward > 0) == (theirs["reward"] > 0)
            rows.append(
                {
                    "domain": domain,
                    "task_id": tid,
                    "variant": variant.value,
                    "holdout": holdout(tid),
                    "ours_reward": ours.reward,
                    "gold_reward": theirs["reward"],
                    "agree": agree,
                    "ours_db": ours.db_match,
                    "gold_db": theirs["db"] > 0,
                    "ours_action": ours.action_match,
                    "gold_action": theirs["action"] > 0,
                    "ours_comm": ours.communicate_match,
                    "gold_comm": theirs["communicate"] > 0,
                }
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{domain}.rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return summarize(rows)


def summarize(rows: list[dict]) -> dict:
    by_variant = defaultdict(lambda: [0, 0])
    by_domain = defaultdict(lambda: [0, 0])
    split = {"dev": [0, 0], "holdout": [0, 0]}
    fails = []
    for r in rows:
        bucket = by_variant[r["variant"]]
        bucket[1] += 1
        bucket[0] += int(r["agree"])
        d = by_domain[r["domain"]]
        d[1] += 1
        d[0] += int(r["agree"])
        s = split["holdout"] if r["holdout"] else split["dev"]
        s[1] += 1
        s[0] += int(r["agree"])
        if not r["agree"]:
            fails.append(r)
    total = [sum(v[0] for v in by_domain.values()), sum(v[1] for v in by_domain.values())]
    return {
        "agreement": total[0] / total[1] if total[1] else 0.0,
        "n": total[1],
        "by_variant": {k: round(v[0] / v[1], 4) for k, v in sorted(by_variant.items())},
        "by_domain": {k: round(v[0] / v[1], 4) for k, v in by_domain.items()},
        "dev_agreement": round(split["dev"][0] / split["dev"][1], 4),
        "holdout_agreement": round(split["holdout"][0] / split["holdout"][1], 4),
        "disagreements": fails[:50],
    }


def main() -> None:
    t0 = time.time()
    out_dir = REPO / "results" / "n1"
    report = {}
    for d in DOMAINS:
        rep = run(d, out_dir)
        report[d] = rep
        print(f"[{d}] agreement={rep['by_domain'].get(d)}")
    all_rows = []
    for d in DOMAINS:
        all_rows.extend(json.load(open(out_dir / f"{d}.rows.json", encoding="utf-8")))
    overall = summarize(all_rows)
    report["_overall"] = {k: v for k, v in overall.items() if k != "disagreements"}
    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in overall.items() if k != "disagreements"}, indent=1))
    dis = overall["disagreements"]
    print(f"disagreements: {len(dis)} shown:")
    for r in dis[:15]:
        print(" ", r["domain"], r["task_id"], r["variant"], "ours", r["ours_reward"], "gold", r["gold_reward"])
    print(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
