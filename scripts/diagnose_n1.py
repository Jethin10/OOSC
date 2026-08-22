"""Diagnose N1 disagreement cases: dump both sides' component details."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))

from oosc.adapters.corruptions import Variant, corrupt  # noqa: E402
from oosc.adapters.tau2_gold import gold_reward, make_task_lookup  # noqa: E402
from oosc.oracle import Oracle, TrajectoryStep  # noqa: E402
from oosc.schema import DomainDef, TaskCriteria  # noqa: E402
from oosc.world.world import MockWorld  # noqa: E402

SCHEMA_DIR = REPO / "results" / "repro" / "schema"


def diagnose(domain: str, task_id: str, variants: list[str]) -> None:
    dom = DomainDef.model_validate(json.load(open(SCHEMA_DIR / f"{domain}.domain.json", encoding="utf-8")))
    norm_tasks = {t["id"]: t for t in json.load(open(SCHEMA_DIR / f"{domain}.tasks.json", encoding="utf-8"))}
    nt = norm_tasks[task_id]
    task = make_task_lookup(domain)[task_id]
    oracle = Oracle(dom)
    crit = TaskCriteria(
        actions=nt["criteria"]["actions"],
        communicate_info=nt["criteria"]["communicate_info"],
        reward_basis=[b for b in nt["criteria"]["reward_basis"] if b != "NL_ASSERTION"] or ["DB"],
    )
    print(f"=== {domain}/{task_id} basis={crit.reward_basis}")
    for i, a in enumerate(crit.actions):
        print(f"  gold[{i}] {a.name} {json.dumps(a.arguments)[:120]}")
    for vname in variants:
        rng = random.Random(f"{domain}:{task_id}:{vname}")
        steps = corrupt(Variant(vname), crit.actions, crit.communicate_info, dom, rng)
        ours = oracle.grade(crit, steps)
        theirs = gold_reward(task, steps, domain)
        print(f"--- variant={vname}: ours={ours.reward} gold={theirs['reward']}")
        print(f"    ours details: {json.dumps(ours.details)[:400]}")
        print(f"    gold comps: db={theirs['db']} action={theirs['action']} comm={theirs['communicate']}")
        # our world views
        pw = MockWorld(oracle.spec)
        for s in steps:
            for c in s.calls:
                r = pw.call(c["name"], c["arguments"])
                if not r.ok:
                    print(f"      pred-call ERR {c['name']}: {r.error}")
        gw = MockWorld(oracle.spec)
        for a in crit.actions:
            gw.call(a.name, dict(a.arguments))
        pl, gl = pw.compressed_ledger(), gw.compressed_ledger()
        print(f"    pred ledger ({len(pl)}): {[ (e['tool'], e['args']) for e in pl ]}"[:500])
        print(f"    gold ledger ({len(gl)}): {[ (e['tool'], e['args']) for e in gl ]}"[:500])


if __name__ == "__main__":
    domain, task_id = sys.argv[1], sys.argv[2]
    diagnose(domain, task_id, sys.argv[3:])
