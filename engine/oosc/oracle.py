"""Our oracle: grades a trajectory against task criteria using the DERIVED world.

Component semantics mirror tau2-bench's evaluator (DECISIONS.md D3):
- DB:        final-state equivalence - gold actions replayed in a fresh MockWorld
             vs the trajectory replayed in another fresh MockWorld, compared by
             compressed-ledger fingerprint.
- ACTION:    every golden action is matched by some call (exact name; argument
             equality over compare_args, defaulting to the call's own keys).
- COMMUNICATE: case-insensitive substring of each info string in some assistant
             text (commas stripped), matching their implementation.
NL_ASSERTION is excluded symmetrically from both oracles (needs an LLM judge).

Reward = product of the components listed in reward_basis (deterministic ones).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oosc.schema import ActionDef, DomainDef, TaskCriteria
from oosc.world.derive import WorldSpec
from oosc.world.world import MockWorld


@dataclass
class TrajectoryStep:
    """One agent turn: optional text plus tool calls."""

    text: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)  # {name, arguments}


@dataclass
class Verdict:
    db_match: bool
    action_match: bool
    communicate_match: bool
    reward: float
    details: dict[str, Any] = field(default_factory=dict)


def _args_match(golden: ActionDef, call_args: dict[str, Any]) -> bool:
    compare_keys = (
        golden.compare_args if golden.compare_args is not None else list(call_args.keys())
    )
    if len(compare_keys) == 0:
        return True
    tool_args = {k: v for k, v in call_args.items() if k in set(compare_keys)}
    action_args = {k: v for k, v in golden.arguments.items() if k in set(compare_keys)}
    return tool_args == action_args


class Oracle:
    def __init__(self, domain: DomainDef):
        self.domain = domain
        self._spec = WorldSpec(domain)

    @property
    def spec(self) -> WorldSpec:
        return self._spec

    def _replay(self, steps: list[TrajectoryStep]) -> tuple[MockWorld, list[dict]]:
        world = MockWorld(self._spec)
        calls: list[dict] = []
        for step in steps:
            for c in step.calls:
                world.call(c["name"], dict(c.get("arguments") or {}))
                calls.append({"name": c["name"], "arguments": dict(c.get("arguments") or {})})
        return world, calls

    def grade(
        self,
        criteria: TaskCriteria,
        steps: list[TrajectoryStep],
        basis: list[str] | None = None,
    ) -> Verdict:
        basis = basis if basis is not None else criteria.reward_basis
        pred_world, calls = self._replay(steps)
        gold_steps = [
            TrajectoryStep(
                text="",
                calls=[{"name": a.name, "arguments": dict(a.arguments)} for a in criteria.actions],
            )
        ]
        gold_world, _ = self._replay(gold_steps)

        db_match = pred_world.fingerprint() == gold_world.fingerprint()

        action_checks = []
        for g in criteria.actions:
            matched = any(
                g.name == c["name"]
                and (g.requestor == "assistant" or True)  # requestor kept for parity
                and _args_match(g, c["arguments"])
                for c in calls
            )
            action_checks.append(matched)
        action_match = all(action_checks)

        comm_match = True
        missing: list[str] = []
        texts = [s.text for s in steps if s.text]
        for info in criteria.communicate_info:
            needle = info.lower()
            if not any(needle in t.lower().replace(",", "") for t in texts):
                comm_match = False
                missing.append(info)

        reward = 1.0
        if "DB" in basis:
            reward *= 1.0 if db_match else 0.0
        if "ACTION" in basis:
            reward *= 1.0 if action_match else 0.0
        if "COMMUNICATE" in basis:
            reward *= 1.0 if comm_match else 0.0

        return Verdict(
            db_match=db_match,
            action_match=action_match,
            communicate_match=comm_match,
            reward=reward,
            details={
                "missing_comm": missing,
                "action_checks": action_checks,
                "pred_fp": pred_world.fingerprint(),
                "gold_fp": gold_world.fingerprint(),
                "pred_mutations": len(pred_world.ledger),
                "gold_mutations": len(gold_world.ledger),
            },
        )
