"""Scripted agent policies with parameterized flaws.

They exist so CI runs are deterministic and cheap (no LLM): each policy
deterministically exhibits one of the production failure modes the engine must
catch, plus a clean control. Live-model agents plug into the same interface:
``act(scenario, view) -> steps``.
"""

from __future__ import annotations

from typing import Any

from oosc.oracle import TrajectoryStep
from oosc.schema import Scenario


def _criteria_steps(scenario: Scenario) -> list[TrajectoryStep]:
    return [
        TrajectoryStep(calls=[{"name": a.name, "arguments": dict(a.arguments)}])
        for a in scenario.criteria.actions
    ]


class CleanAgent:
    """Executes exactly what the scenario asks. Control group."""

    name = "clean-agent"

    def act(self, scenario: Scenario) -> list[TrajectoryStep]:
        steps = _criteria_steps(scenario)
        if scenario.instructions:
            steps.append(TrajectoryStep(text="Done - I took care of that for you."))
        return steps


class LoopyAgent:
    """Repeats every mutating call three times - the classic retry loop."""

    name = "loopy-agent"

    def act(self, scenario: Scenario) -> list[TrajectoryStep]:
        out: list[TrajectoryStep] = []
        for step in _criteria_steps(scenario):
            out.append(step)
            for c in step.calls:
                out.extend([TrajectoryStep(calls=[dict(c)]) for _ in range(2)])
        return out


class OverconfidentAgent:
    """Does the work but botches the last call, then claims success anyway."""

    name = "overconfident-agent"

    def act(self, scenario: Scenario) -> list[TrajectoryStep]:
        steps = _criteria_steps(scenario)
        if steps:
            last = steps[-1]
            broken = [dict(c) for c in last.calls]
            for c in broken:
                c["arguments"] = {**c.get("arguments", {})}
                for k in c["arguments"]:
                    if isinstance(c["arguments"][k], str):
                        c["arguments"][k] = c["arguments"][k] + "-typo"
                        break
            steps[-1] = TrajectoryStep(calls=broken)
        steps.append(TrajectoryStep(text="All done! Everything was cancelled and refunded successfully."))
        return steps


class RecklessAgent:
    """Completes the task, then also cancels an unrelated entity 'for convenience'."""

    name = "reckless-agent"

    def __init__(self, domain: "Any" = None):
        from oosc.schema import DomainDef  # local import to avoid cycle at module import

        self.domain = domain

    def act(self, scenario: Scenario) -> list[TrajectoryStep]:
        steps = _criteria_steps(scenario)
        used = set()
        for s in steps:
            for c in s.calls:
                used.update(str(v) for v in c.get("arguments", {}).values() if isinstance(v, str))
        victim = None
        if self.domain is not None:
            cancel_tool = next((t.name for t in self.domain.tools if t.name.startswith("cancel_")), None)
            id_param = None
            if cancel_tool:
                id_param = next((p.name for p in self.domain.tool(cancel_tool).params if p.name.endswith("_id")), None)
            if cancel_tool and id_param:
                stem = id_param[: -len("_id")]
                want = stem if stem.endswith("s") else stem + "s"
                from oosc.world.derive import WorldSpec

                eff = WorldSpec(self.domain).effects.get(cancel_tool)
                req = eff.required_statuses if eff else set()
                for table in self.domain.tables:
                    if table.name != want:
                        continue
                    key = next((c for c in (table.records[0] if table.records else {}) if c.endswith("_id") or c == "id"), None)
                    for rec in table.records:
                        v = rec.get(key) if key else None
                        status = str(rec.get("status", "")).lower()
                        ok_status = (not req) or status in req
                        if isinstance(v, str) and v not in used and ok_status:
                            victim = (id_param, v, cancel_tool)
                            break
                    if victim:
                        break
        if victim is None:
            return steps
        k, v, tool = victim
        args: dict[str, Any] = {k: v}
        td = self.domain.tool(tool)
        for p in td.params:
            if p.required and p.name not in args:
                args[p.name] = "no longer needed" if "reason" in p.name else f"gen_{p.name}"
        steps.append(TrajectoryStep(calls=[{"name": tool, "arguments": args}]))
        steps.append(TrajectoryStep(text="Also cleaned up that other order for you."))
        return steps
