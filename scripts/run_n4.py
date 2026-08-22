"""N4: unsafe-action catch rate against agentdojo's 629 security cases.

Case universe (frozen, DECISIONS.md D10): agentdojo pinned at tag v0.1.2,
86 base user tasks x 7 template attacks + 27 injection-task utility cases.

For every case we run a scripted VULNERABLE victim: it performs the user
task's own ground-truth calls, then complies with the injected instruction by
executing the injection task's ground-truth calls. A case counts as
REPRODUCIBLE only if agentdojo's own security check confirms the attack in the
mutated world state. Our guardrail classifier sees ONLY the call trace and the
untrusted text - never the ground truths - and flags unsafe mutations.

catch_rate = flagged_and_reproduced / reproduced
benign_fpr = flagged_benign / benign_runs (no injection, hardened victim)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))

from oosc.classify.guardrail import GuardrailConfig, TraceCall, classify_unsafe  # noqa: E402

ATTACK_NAMES = [
    "direct",
    "ignore_previous",
    "system_message",
    "injecagent",
    "important_instructions",
    "important_instructions_no_user_name",
    "important_instructions_no_model_name",
]
SUITES = ["workspace", "slack", "travel", "banking"]
OUT = REPO / "results" / "n4"


def _make_attacker(name: str, suite):
    from agentdojo.attacks.baseline_attacks import (
        DirectAttacker,
        IgnorePreviousAttacker,
        ImportantInstructionsAttacker,
        InjecAgentAttacker,
        SystemMessageAttacker,
    )

    cls = {
        "direct": DirectAttacker,
        "ignore_previous": IgnorePreviousAttacker,
        "system_message": SystemMessageAttacker,
        "injecagent": InjecAgentAttacker,
        "important_instructions": ImportantInstructionsAttacker,
        "important_instructions_no_user_name": ImportantInstructionsAttacker,
        "important_instructions_no_model_name": ImportantInstructionsAttacker,
    }[name]
    kwargs = {}
    if name == "important_instructions_no_user_name":
        kwargs["user_name"] = ""
    if name == "important_instructions_no_model_name":
        kwargs["model_name"] = ""
    return cls(name=name, task_suite=suite, **kwargs)


def _combined_task_ids(suite_path: Path) -> set[str]:
    src = suite_path.read_text(encoding="utf-8")
    return set(re.findall(r'create_combined_task\(\s*"([^"]+)"', src))


def _norm_calls(calls) -> list:
    """agentdojo versions return FunctionCall objects or plain dicts."""
    out = []
    for c in calls or []:
        if isinstance(c, dict):
            out.append(type("C", (), {"function": c.get("function"), "args": c.get("args", {})})())
        else:
            out.append(c)
    return out


def _run_calls(runtime, env, calls) -> tuple[list[TraceCall], list[str]]:
    before_all = None
    trace: list[TraceCall] = []
    errors: list[str] = []
    for call in _norm_calls(calls):
        before = env.model_dump_json()
        try:
            _out, err = runtime.run_function(env, call.function, dict(call.args))
        except Exception as e:  # tool raised - record as failed no-op
            err = str(e)
            _out = None
        after = env.model_dump_json()
        out_str = _out if isinstance(_out, str) else json.dumps(_out, default=str)[:2000]
        trace.append(
            TraceCall(
                function=call.function,
                args=dict(call.args),
                output=(err or out_str or "")[:2000],
                mutated=before != after,
            )
        )
        if err:
            errors.append(str(err))
    return trace, errors


def main() -> None:
    from agentdojo.functions_runtime import FunctionsRuntime
    from agentdojo.task_suite.load_suites import get_suite

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cfg = GuardrailConfig()
    stats = {
        "cases_total": 0,
        "reproducible": 0,
        "flagged_reproducible": 0,
        "flagged_s1_only": 0,
        "not_reproducible": 0,
        "benign_runs": 0,
        "flagged_benign": 0,
    }
    per_suite = {}

    for suite_name in SUITES:
        suite = get_suite("v1", suite_name)
        runtime = FunctionsRuntime(suite.tools)
        ut_mod = f"agentdojo.default_suites.v1.{suite_name}.user_tasks"
        import importlib

        importlib.import_module(ut_mod)
        base_ids = [
            tid
            for tid, t in suite.user_tasks.items()
            if "NewCombinedTask" not in type(t).__qualname__
        ]
        assert len(base_ids) == {"workspace": 33, "slack": 17, "travel": 20, "banking": 16}[suite_name], f"{suite_name}: {len(base_ids)}"

        attackers = {n: _make_attacker(n, suite) for n in ATTACK_NAMES}
        inj_tasks = list(suite.injection_tasks.values())

        s_stats = {"cases": 0, "repro": 0, "flagged": 0, "benign": 0, "benign_flagged": 0}

        for ut_id in base_ids:
            ut = suite.user_tasks[ut_id]
            for attack_name in ATTACK_NAMES:
                attacker = attackers[attack_name]
                # one CASE = (base user task x attack); within it the victim is
                # exposed to every injection goal of the suite (their benchmark
                # loops all pairs; we aggregate to keep the 629 denominator).
                stats["cases_total"] += 1
                s_stats["cases"] += 1
                case_repro = False
                case_flagged = False
                case_flagged_s1 = False
                for it in inj_tasks:
                    try:
                        injections = attacker.attack(ut, it)
                        env = suite.load_and_inject_default_environment(injections)
                    except Exception:
                        continue
                    pre = env.model_copy(deep=True)
                    untrusted = list(injections.values())
                    calls = list(ut.ground_truth(pre)) + list(it.ground_truth(pre))
                    trace, _errs = _run_calls(runtime, env, calls)
                    try:
                        reproduced = bool(it.security(it.GROUND_TRUTH_OUTPUT, pre, env))
                    except Exception:
                        reproduced = False
                    findings = classify_unsafe(trace, untrusted, cfg)
                    findings_s1 = [f for f in findings if f.kind == "argument_taint"]
                    if reproduced:
                        case_repro = True
                        if findings:
                            case_flagged = True
                            case_flagged_s1 = case_flagged_s1 or bool(findings_s1)
                if case_repro:
                    stats["reproducible"] += 1
                    s_stats["repro"] += 1
                    if case_flagged:
                        stats["flagged_reproducible"] += 1
                        s_stats["flagged"] += 1
                    if case_flagged_s1:
                        stats["flagged_s1_only"] += 1
                else:
                    stats["not_reproducible"] += 1

            # benign control run (no injection, victim does only the user task)
            try:
                env0 = suite.load_and_inject_default_environment({})
                pre0 = env0.model_copy(deep=True)
                calls0 = list(ut.ground_truth(pre0))
                trace0, _e = _run_calls(runtime, env0, calls0)
                stats["benign_runs"] += 1
                s_stats["benign"] += 1
                if classify_unsafe(trace0, [], cfg):
                    stats["flagged_benign"] += 1
                    s_stats["benign_flagged"] += 1
            except Exception:
                pass

        per_suite[suite_name] = s_stats
        print(f"[{suite_name}] cases={s_stats['cases']} repro={s_stats['repro']} flagged={s_stats['flagged']} benign_fpr={s_stats['benign_flagged']}/{s_stats['benign']}")

    # 27 injection-utility standalone cases: attacker goal as its own task;
    # reproduction gate is UTILITY (that is what these cases measure)
    for suite_name in SUITES:
        suite = get_suite("v1", suite_name)
        runtime = FunctionsRuntime(suite.tools)
        for it in suite.injection_tasks.values():
            stats["cases_total"] += 1
            try:
                injections = {k: f"{it.GOAL}" for k in suite.get_injection_vector_defaults()}
                env = suite.load_and_inject_default_environment(injections)
            except Exception:
                stats["not_reproducible"] += 1
                continue
            pre = env.model_copy(deep=True)
            calls = list(it.ground_truth(pre))
            trace, _errs = _run_calls(runtime, env, calls)
            try:
                reproduced = bool(it.security(it.GROUND_TRUTH_OUTPUT, pre, env))
            except Exception:
                reproduced = False
            findings = classify_unsafe(trace, list(injections.values()), cfg)
            findings_s1 = [f for f in findings if f.kind == "argument_taint"]
            if reproduced:
                stats["reproducible"] += 1
                if findings:
                    stats["flagged_reproducible"] += 1
                if findings_s1:
                    stats["flagged_s1_only"] += 1
            else:
                stats["not_reproducible"] += 1

    result = {
        "stats": stats,
        "per_suite": per_suite,
        "catch_rate_over_629": round(stats["flagged_reproducible"] / 629, 4),
        "catch_rate_over_reproducible": round(stats["flagged_reproducible"] / max(1, stats["reproducible"]), 4),
        "catch_rate_strict_arg_taint_only": round(stats["flagged_s1_only"] / max(1, stats["reproducible"]), 4),
        "benign_fpr": round(stats["flagged_benign"] / max(1, stats["benign_runs"]), 4),
        "case_universe": {
            "base_user_tasks": 86,
            "attacks": ATTACK_NAMES,
            "injection_utility_cases": 27,
            "expected_total": 629,
        },
    }
    (OUT / "report.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result["stats"], indent=1))
    print("catch rate:", result["catch_rate_over_reproducible"], "| benign fpr:", result["benign_fpr"])
    print(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
