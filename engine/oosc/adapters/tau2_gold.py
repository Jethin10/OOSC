"""Compute GOLD rewards with tau2-bench's own evaluators.

This is metric harness plumbing only - it exists so the agreement number can be
measured against their implementation, not ours. The world derivation never
imports anything from here (import-lint test enforces the boundary).

We call the three deterministic component evaluators directly and combine them
per the task's reward_basis minus NL_ASSERTION, mirroring tau2's ALL evaluation
(DECISIONS.md D3). Trajectories are executed once against a real environment to
record genuine tool outputs, then graded via set_state replay with
strict_replay=False - the same lenient mode tau2 ships for re-grading.
"""

from __future__ import annotations

import json
from typing import Any

from oosc.oracle import TrajectoryStep


def _to_messages(env: Any, steps: list[TrajectoryStep]) -> list[Any]:
    """Execute steps against a live tau2 env, recording real outputs."""
    from tau2.data_model.message import (
        AssistantMessage,
        ToolCall,
        ToolMessage,
    )

    messages: list[Any] = []
    n = 0
    for step in steps:
        if step.text:
            messages.append(AssistantMessage(role="assistant", content=step.text))
        for c in step.calls:
            n += 1
            cid = f"call_{n}"
            tc = ToolCall(id=cid, name=c["name"], arguments=dict(c.get("arguments") or {}))
            try:
                out = env.make_tool_call(tool_name=c["name"], requestor="assistant", **dict(c.get("arguments") or {}))
                content = out if isinstance(out, str) else json.dumps(out)
                err = False
            except Exception as e:  # noqa: BLE001 - record failure like the live env does
                content = str(e)
                err = True
            messages.append(AssistantMessage(role="assistant", content=None, tool_calls=[tc]))
            messages.append(
                ToolMessage(
                    id=cid,
                    role="tool",
                    content=content,
                    requestor="assistant",
                    error=err,
                )
            )
    return messages


def gold_reward(task: Any, steps: list[TrajectoryStep], domain: str) -> dict[str, Any]:
    """Grade one trajectory with tau2's deterministic component evaluators."""
    from tau2.evaluator.evaluator_action import ActionEvaluator
    from tau2.evaluator.evaluator_communicate import CommunicateEvaluator
    from tau2.evaluator.evaluator_env import EnvironmentEvaluator

    from tau2.registry import registry

    ctor = registry.get_env_constructor(domain)
    live = ctor(solo_mode=False)
    messages = _to_messages(live, steps)

    crit = task.evaluation_criteria
    basis = {str(b.value if hasattr(b, "value") else b) for b in (crit.reward_basis or [])}

    env_info = EnvironmentEvaluator.calculate_reward(
        environment_constructor=ctor,
        task=task,
        full_trajectory=messages,
        solo_mode=False,
        strict_replay=False,
    )
    act_info = ActionEvaluator.calculate_reward(task=task, full_trajectory=messages, tool_types=None)
    comm_info = CommunicateEvaluator.calculate_reward(task=task, full_trajectory=messages)

    reward = 1.0
    if "DB" in basis:
        reward *= env_info.reward
    if "ACTION" in basis:
        reward *= act_info.reward
    if "COMMUNICATE" in basis:
        reward *= comm_info.reward
    return {
        "reward": reward,
        "db": env_info.reward,
        "action": act_info.reward,
        "communicate": comm_info.reward,
        "basis": sorted(basis),
    }


def make_task_lookup(domain: str) -> dict[str, Any]:
    from tau2.registry import registry

    return {t.id: t for t in registry.get_tasks_loader(domain)()}
