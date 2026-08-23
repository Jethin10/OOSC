"""Sandboxed execution with traces good enough for deterministic replay.

A RunTrace records every step (text, calls, per-call world verdicts and state
fingerprints). ``verify_replay`` re-executes a trace against a fresh MockWorld
and asserts identical fingerprints after each mutating call - if any recorded
outcome cannot be reproduced, replay fails. This is what makes runs auditable:
a scorecard number can always be traced back to an exact, re-runnable history.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from oosc.oracle import Oracle, TrajectoryStep, Verdict
from oosc.schema import DomainDef, TaskCriteria
from oosc.world.world import MockWorld


@dataclass
class TraceCallRecord:
    name: str
    arguments: dict[str, Any]
    ok: bool
    error: str | None = None
    mutated: bool = False
    fingerprint_after: str | None = None


@dataclass
class RunTrace:
    scenario_id: str
    domain: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    final_fingerprint: str | None = None
    verdict: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, default=str)

    @staticmethod
    def from_json(blob: str) -> "RunTrace":
        d = json.loads(blob)
        t = RunTrace(scenario_id=d["scenario_id"], domain=d["domain"])
        t.steps = d["steps"]
        t.final_fingerprint = d.get("final_fingerprint")
        t.verdict = d.get("verdict")
        return t


class Sandbox:
    def __init__(self, domain: DomainDef):
        self.domain = domain
        self.oracle = Oracle(domain)

    def run(
        self,
        scenario_id: str,
        steps: list[TrajectoryStep],
        criteria: TaskCriteria,
        record_verdict: bool = True,
    ) -> tuple[RunTrace, Verdict]:
        world = MockWorld(self.oracle.spec)
        trace = RunTrace(scenario_id=scenario_id, domain=self.domain.name)
        for si, step in enumerate(steps):
            rec_calls = []
            entry = {"step": si, "text": step.text or "", "calls": rec_calls}
            trace.steps.append(entry)
            for c in step.calls:
                res = world.call(c["name"], dict(c.get("arguments") or {}))
                rec_calls.append(
                    {
                        "name": c["name"],
                        "arguments": c.get("arguments") or {},
                        "ok": res.ok,
                        "error": res.error,
                        "mutated": res.mutated,
                        "output": str(c.get("mock_output") or ""),
                        "fingerprint_after": world.fingerprint() if res.mutated else None,
                    }
                )
        trace.final_fingerprint = world.fingerprint()
        verdict = self.oracle.grade(criteria, steps)
        if record_verdict:
            trace.verdict = {
                "reward": verdict.reward,
                "db_match": verdict.db_match,
                "action_match": verdict.action_match,
                "communicate_match": verdict.communicate_match,
            }
        return trace, verdict


def verify_replay(domain: DomainDef, trace: RunTrace) -> tuple[bool, list[str]]:
    """Re-execute a trace against a fresh world; every recorded fingerprint
    must reproduce exactly."""
    world = MockWorld(Oracle(domain).spec)
    problems: list[str] = []
    for step in trace.steps:
        for c in step.get("calls", []):
            res = world.call(c["name"], dict(c.get("arguments") or {}))
            if res.ok != c.get("ok", True):
                problems.append(f"{c['name']}: ok={res.ok} recorded={c.get('ok')}")
            fp = world.fingerprint()
            if c.get("fingerprint_after") is not None and c["fingerprint_after"] != fp:
                problems.append(f"{c['name']}: fingerprint divergence at mutation")
    if trace.final_fingerprint is not None and world.fingerprint() != trace.final_fingerprint:
        problems.append("final fingerprint mismatch")
    return (len(problems) == 0), problems
