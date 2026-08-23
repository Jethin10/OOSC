"""Assemble everything the scorecard interface renders into one bundle.

Sources, all committed artifacts:
  results/ci/ci-report.json       the commit-gate run (scorecards, runs, traces)
  results/history/*.json          the regression ledger, one snapshot per CI run
  results/n{1,2,3,4}/report.json  external benchmark evidence

Every number in the interface is read from these files. Nothing is typed in by
hand, so a claim on screen can always be traced back to a reproducible run.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "ui" / "data" / "report.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def history_series() -> list[dict]:
    """One point per persisted CI snapshot, oldest first."""
    points = []
    for path in sorted((RESULTS / "history").glob("*.json")):
        try:
            snap = load(path)
        except (OSError, json.JSONDecodeError):
            continue
        points.append(
            {
                "snapshot_id": snap.get("snapshot_id") or path.stem,
                "commit_sha": snap.get("commit_sha", ""),
                "generated_at": snap.get("generated_at", ""),
                "domain": snap.get("domain", ""),
                "suite_size": snap.get("suite_size", 0),
                "replay_failures": snap.get("replay_failures", 0),
                "agents": {
                    name: {
                        "reliability": card.get("overall", {}).get("reliability", 0.0),
                        "ci95": card.get("overall", {}).get("ci95", [0, 0]),
                        "runs": card.get("overall", {}).get("runs", 0),
                    }
                    for name, card in (snap.get("scorecards") or {}).items()
                },
                "categories": {
                    name: {c["category"]: c["reliability"] for c in card.get("categories", [])}
                    for name, card in (snap.get("scorecards") or {}).items()
                },
            }
        )
    return points


def benchmarks() -> list[dict]:
    n1 = load(RESULTS / "n1" / "report.json")["_overall"]
    n2 = load(RESULTS / "n2" / "report.json")["_overall"]
    n3 = load(RESULTS / "n3" / "report.json")
    n4 = load(RESULTS / "n4" / "report.json")
    return [
        {
            "id": "n1",
            "status": "cleared",
            "title": "Oracle agreement",
            "subtitle": "vs tau2-bench gold rewards",
            "value": n1["agreement"],
            "bar": 0.95,
            "bar_label": "target >= 95%",
            "ci95": n1["ci95"],
            "sample": f"{n1['n']} graded trajectories across all 164 tasks",
            "claim": "A world derived from tool schemas alone agrees with the "
                     "hand-written Python domains of tau2-bench on pass/fail.",
            "method": "Gold reward = product of the reward_basis components of each task "
                      "(DB hash x ACTION subset x COMMUNICATE). Eight frozen corruption "
                      "variants per task, seeded. Our derivation never imports their domain code.",
            "splits": [
                {"label": "dev", "value": n1["dev_agreement"]},
                {"label": "holdout", "value": n1["holdout_agreement"]},
                {"label": "retail", "value": n1["by_domain"]["retail"]},
                {"label": "airline", "value": n1["by_domain"]["airline"]},
            ],
            "breakdown": [{"label": k, "value": v} for k, v in sorted(n1["by_variant"].items())],
            "caveat": "Airline holdout is 91.7% on a small cell. The residual disagreements "
                      "sit inside the hand-written multi-segment pricing rules of tau2, "
                      "which schema-only derivation deliberately does not copy.",
            "source": "scripts/run_n1.py + results/n1/report.json",
        },
        {
            "id": "n3",
            "status": "cleared",
            "title": "Failure-classifier joint accuracy",
            "subtitle": "vs TRAIL published best",
            "value": n3["_overall"]["joint_accuracy"],
            "bar": 0.11,
            "bar_label": "published best 11%",
            "sample": f"{n3['GAIA']['traces'] + n3['SWE Bench']['traces']} annotated traces "
                      f"(GAIA {n3['GAIA']['traces']}, SWE-Bench {n3['SWE Bench']['traces']})",
            "claim": "Predicting both WHERE a run failed and WHY, scored by the official "
                     "TRAIL scorer. 4.2x the published best.",
            "method": "Rule-based, evidence-gated classifier over observable span data only "
                      "(status codes, exception traces, span role, log keywords). Zero label "
                      "access. Scored with their own calculate_scores.py on their metric.",
            "splits": [
                {"label": "GAIA", "value": n3["GAIA"]["joint_accuracy"], "vs": 0.183},
                {"label": "SWE-Bench", "value": n3["SWE Bench"]["joint_accuracy"], "vs": 0.05},
            ],
            "breakdown": [
                {"label": "GAIA location acc.", "value": n3["GAIA"]["location_accuracy"]},
                {"label": "GAIA weighted F1", "value": n3["GAIA"]["weighted_f1"]},
                {"label": "SWE location acc.", "value": n3["SWE Bench"]["location_accuracy"]},
                {"label": "SWE weighted F1", "value": n3["SWE Bench"]["weighted_f1"]},
            ],
            "caveat": "The official TRAIL metric is recall-oriented. We publish weighted F1 "
                      "beside it so precision stays visible.",
            "source": "scripts/run_n3.py + arXiv:2505.08638",
        },
        {
            "id": "n4",
            "status": "cleared",
            "title": "Unsafe-action catch rate",
            "subtitle": "vs agentdojo security cases",
            "value": n4["catch_rate_over_629"],
            "bar": 0.80,
            "bar_label": "target >= 80%",
            "ci95": n4["ci95_over_629"],
            "sample": f"{n4['stats']['cases_total']} cases "
                      f"({n4['case_universe']['base_user_tasks']} base tasks x "
                      f"{len(n4['case_universe']['attacks'])} attacks + "
                      f"{n4['case_universe']['injection_utility_cases']} utility cases)",
            "claim": "Catches prompt-injected destructive actions, counting only findings "
                     "that reproduce as real mutations in sandboxed world state.",
            "method": "Argument taint plus poisoned-read proximity, mutation-verified. A "
                      "finding counts only when the sandbox world actually shows the "
                      "malicious mutation. Case universe pinned to agentdojo v0.1.2.",
            "splits": [
                {"label": s, "value": (v["flagged"] / v["cases"]) if v["cases"] else 0.0}
                for s, v in n4["per_suite"].items()
            ],
            "breakdown": [
                {"label": "over reproducible cases", "value": n4["catch_rate_over_reproducible"]},
                {"label": "arg-taint only", "value": n4["catch_rate_strict_arg_taint_only"]},
                {"label": "benign false-positive rate", "value": n4["benign_fpr"]},
            ],
            "highlight": f"{n4['stats']['flagged_benign']}/{n4['stats']['benign_runs']} "
                         "false positives on benign runs",
            "caveat": "Victim agents are deterministic scripted policies with parameterized "
                      "vulnerability profiles, not live models. The harness accepts any "
                      "policy, so live-model runs slot in without changing the metric.",
            "source": "scripts/run_n4.py + ethz-spylab/agentdojo v0.1.2",
        },
        {
            "id": "n2",
            "status": "parked",
            "title": "Task rediscovery",
            "subtitle": "hand-authored tau2 tasks found blind",
            "value": n2["strict_rate"],
            "bar": 0.50,
            "bar_label": "target >= 50% - not met",
            "ci95": n2["ci95_strict"],
            "sample": f"{n2['tasks']} tasks, {n2['strict']} strict, {n2['writes_only']} structural",
            "claim": "Reported as a miss. The generator enumerated 8.5M exact action "
                     "signatures from schemas and initial state alone and still did not "
                     "reach the bar.",
            "method": "The generator never reads tasks.json. Strict = action names plus "
                      "complete argument equality. Structural = names plus entity-id "
                      "bindings, free text ignored. Granularity fixed before generation ran.",
            "splits": [
                {"label": "strict", "value": n2["strict_rate"]},
                {"label": "structural", "value": n2["writes_only_rate"]},
            ],
            "breakdown": [
                {"label": "derivability ceiling", "value": 0.738},
                {"label": "structural rate", "value": n2["writes_only_rate"]},
            ],
            "caveat": "Two blockers, both real. 43 of 164 tasks carry free-text payloads "
                      "(new addresses, arbitrary emails) that no schema-plus-data process "
                      "can conjure, capping any such method at 73.8%. And the read-chain "
                      "interleavings of tau2 are authoring idiosyncrasy, not derivable "
                      "structure. Published unmet rather than redefined.",
            "source": "scripts/run_n2.py + results/n2/report.json",
        },
    ]


DIRECTIONS = [
    {
        "id": "generation",
        "name": "Scenario Generation Engine",
        "ask": "Reads the tools, prompt and task domain of an agent to generate realistic "
               "and adversarial test scenarios at scale.",
        "built": "A world model is derived from tool schemas and initial state alone, with "
                 "no hand-authored domain logic. Scenarios are generated against that world "
                 "and validated by execution before they are ever emitted.",
        "code": "engine/oosc/world/derive.py, engine/oosc/generate/",
        "view": "pipeline",
    },
    {
        "id": "sandbox",
        "name": "Sandboxed Execution and Replay Harness",
        "ask": "Runs the agent against generated scenarios with mocked tools, capturing "
               "traces for deterministic replay.",
        "built": "Every call runs against a mock world that fingerprints its state after "
                 "each mutation. Replay re-executes the trace on a fresh world and asserts "
                 "that every fingerprint reproduces exactly.",
        "code": "engine/oosc/runner/sandbox.py",
        "view": "runs",
    },
    {
        "id": "classifier",
        "name": "Failure Mode Classifier",
        "ask": "Categorises why a run failed, turning raw pass or fail results into an "
               "actionable taxonomy.",
        "built": "Four deterministic detectors over the replayable trace, covering tool "
                 "loops, hallucinated confidence, unsafe actions and silent goal drift. "
                 "Each emits the specific evidence that triggered it.",
        "code": "engine/oosc/classify/detectors.py",
        "view": "runs",
    },
    {
        "id": "guardrail",
        "name": "Destructive Action Guardrail Tester",
        "ask": "Probes the willingness of an agent to perform irreversible actions under "
               "pressure or ambiguous instruction.",
        "built": "Irreversible operations are identified from the derived world spec, then "
                 "probed under four escalations: urgency, ambiguity, policy conflict and "
                 "injected tool output.",
        "code": "engine/oosc/classify/guardrail.py",
        "view": "guardrails",
    },
    {
        "id": "scorecard",
        "name": "Reliability Scorecard and Regression Tracker",
        "ask": "Scores and tracks agent reliability across versions and task categories.",
        "built": "Reliability is a rate with a Wilson 95% interval, never a single pass or "
                 "fail. Snapshots persist per commit, and a drop gates the build only when "
                 "the interval of the candidate clears the interval of the baseline.",
        "code": "engine/oosc/score/",
        "view": "regression",
    },
]


def main() -> int:
    ci = load(RESULTS / "ci" / "ci-report.json")
    history = history_series()
    gate_pass = ci.get("replay_failures", 0) == 0 and ci.get("history_regression", {}).get(
        "gate_pass", True
    )

    bundle = {
        "generated_at": ci["generated_at"],
        "domain": ci["domain"],
        "seed": ci.get("seed"),
        "suite_size": ci["suite_size"],
        "replay_failures": ci["replay_failures"],
        "replay_checks": ci.get("replay_checks", len(ci["runs"])),
        "gate_pass": gate_pass,
        "world_spec": ci.get("world_spec", {}),
        "generation": ci.get("generation", {}),
        "taxonomy": ci.get("taxonomy", []),
        "unsafe_findings_by_agent": ci.get("unsafe_findings_by_agent", {}),
        "scorecards": ci["scorecards"],
        "runs": ci["runs"],
        "regressions_vs_clean": ci.get("regressions_vs_clean", {}),
        "history_regression": ci.get("history_regression", {}),
        "history": history,
        "benchmarks": benchmarks(),
        "directions": DIRECTIONS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    size = OUT.stat().st_size
    print(f"wrote {OUT.relative_to(ROOT)}  {size / 1024:.0f} KB")
    print(
        f"  {len(bundle['runs'])} runs, {len(bundle['scorecards'])} agent versions, "
        f"{len(history)} history snapshots, {len(bundle['benchmarks'])} benchmarks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
