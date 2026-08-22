"""oosc command line interface.

``oosc ci``     generate scenarios, run agent(s) in the sandbox, classify
                failures, verify replayability of every trace, emit scorecards.
                Exit code 1 if reliability gate fails - designed for commits.
``oosc verify`` re-execute a stored trace and check deterministic replay.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from oosc.classify.detectors import detect_all
from oosc.generate.engine import ScenarioGenerator
from oosc.runner.policies import CleanAgent, LoopyAgent, OverconfidentAgent, RecklessAgent
from oosc.runner.sandbox import Sandbox, verify_replay
from oosc.schema import DomainDef
from oosc.score.scorecard import Scorecard


def _load_domain(path: Path) -> DomainDef:
    return DomainDef.model_validate(json.load(open(path, encoding="utf-8")))


def cmd_ci(args: argparse.Namespace) -> int:
    domain = _load_domain(Path(args.domain))
    gen = ScenarioGenerator(domain, seed=args.seed)
    scenarios = gen.generate()
    # bounded, evenly sampled suite for commit-time cost
    step = max(1, len(scenarios) // args.max_scenarios)
    suite = scenarios[::step][: args.max_scenarios]
    if not suite:
        print("no scenarios generated", file=sys.stderr)
        return 2

    policies = [CleanAgent(), LoopyAgent(), OverconfidentAgent(), RecklessAgent(domain)]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    cards: dict[str, dict] = {}
    replay_failures = 0
    for pol in policies:
        if isinstance(pol, RecklessAgent):
            pol.domain = domain
        card = Scorecard(agent_version=pol.name, generated_at=now)
        for sc in suite:
            steps = pol.act(sc)
            sandbox = Sandbox(domain)
            trace, verdict = sandbox.run(sc.id, steps, sc.criteria)
            ok, problems = verify_replay(domain, trace)
            if not ok:
                replay_failures += 1
            intended: set[str] = set()
            for a in sc.criteria.actions:
                for k, v in a.arguments.items():
                    if k.endswith(("_id", "_ids")):
                        vs = v if isinstance(v, list) else [v]
                        intended.update(str(x) for x in vs)
            findings = detect_all(trace.steps, final_reward=verdict.reward, intended_entity_ids=intended)
            kinds = sorted({f.kind for f in findings})
            category = sc.meta.get("op", "unknown")
            success = verdict.reward > 0 and not kinds
            card.record(category, success=success, failure_kinds=kinds if not success else None)
            if args.save_traces:
                (traces_dir / f"{pol.name}-{sc.id}.json").write_text(trace.to_json(), encoding="utf-8")
        cards[pol.name] = card.to_dict()

    result = {
        "suite_size": len(suite),
        "domain": domain.name,
        "replay_failures": replay_failures,
        "scorecards": cards,
    }
    base = cards.get("clean-agent")
    regressions = {}
    for name, c in cards.items():
        if name == "clean-agent":
            continue
        regressions[name] = Scorecard.regression(base or {}, c)
    result["regressions_vs_clean"] = regressions
    (out_dir / "ci-report.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    for name, c in cards.items():
        o = c["overall"]
        print(f"{name:24s} reliability={o['reliability']:.3f} ci95=[{o['ci95'][0]:.3f},{o['ci95'][1]:.3f}] runs={o['runs']}")
    gate_ok = (
        replay_failures == 0
        and cards["overconfident-agent"]["overall"]["reliability"] < cards["clean-agent"]["overall"]["reliability"]
        and cards["reckless-agent"]["overall"]["reliability"] < cards["clean-agent"]["overall"]["reliability"]
    )
    print("gate:", "PASS" if gate_ok else "FAIL")
    return 0 if gate_ok else 1


def cmd_verify(args: argparse.ArgumentParser) -> int:
    from oosc.runner.sandbox import RunTrace

    domain = _load_domain(Path(args.domain))
    trace = RunTrace.from_json(Path(args.trace).read_text(encoding="utf-8"))
    ok, problems = verify_replay(domain, trace)
    print("replay:", "OK" if ok else "FAILED")
    for p in problems:
        print(" -", p)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="oosc")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ci = sub.add_parser("ci", help="run the evaluation suite (commit gate)")
    default_schema = Path(__file__).resolve().parents[2] / "results" / "repro" / "schema" / "retail.domain.json"
    ci.add_argument("--domain", default=str(default_schema))
    ci.add_argument("--out", default="results/ci")
    ci.add_argument("--seed", type=int, default=7)
    ci.add_argument("--max-scenarios", type=int, default=120)
    ci.add_argument("--save-traces", action="store_true")
    ci.set_defaults(fn=cmd_ci)

    vf = sub.add_parser("verify", help="verify deterministic replay of a trace")
    vf.add_argument("--domain", default=str(default_schema))
    vf.add_argument("--trace", required=True)
    vf.set_defaults(fn=cmd_verify)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
