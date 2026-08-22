"""Trajectory corruption taxonomy - FROZEN (DECISIONS.md D4).

These variants were fixed before any agreement measurement. Each applicable
variant is generated once per task with a seeded RNG so every run is
reproducible. The taxonomy intentionally includes classes whose CORRECT gold
reward stays 1.0 (benign reads, idempotent repeats) so we measure false
positives, not just sensitivity.
"""

from __future__ import annotations

import random
import re
from copy import deepcopy
from enum import Enum
from typing import Any, Optional

from oosc.schema import ActionDef, DomainDef, TaskCriteria
from oosc.oracle import TrajectoryStep


class Variant(str, Enum):
    CORRECT = "correct"
    DROP_ACTION = "drop_action"
    WRONG_ARG_VALUE = "wrong_arg_value"
    WRONG_ENTITY = "wrong_entity"
    EXTRA_DESTRUCTIVE = "extra_destructive"
    BENIGN_EXTRA_READ = "benign_extra_read"
    REPEAT_WRITE = "repeat_write"
    SWAP_WRITES = "swap_writes"


_WRITE_HINTS = ("cancel", "modify", "update", "exchange", "return_", "book", "send", "refund")


def is_write(name: str) -> bool:
    return (
        any(h in name for h in _WRITE_HINTS)
        and not name.startswith(("get", "find", "search", "list", "check", "calculate"))
    )


def base_steps(criteria: TaskCriteria) -> list[TrajectoryStep]:
    steps = [
        TrajectoryStep(calls=[{"name": a.name, "arguments": deepcopy(a.arguments)}])
        for a in criteria.actions
    ]
    if criteria.communicate_info:
        steps.append(TrajectoryStep(text=" ".join(criteria.communicate_info)))
    return steps or [TrajectoryStep(text="How can I help?")]


def _steps_from(actions: list[ActionDef], comm: list[str]) -> list[TrajectoryStep]:
    steps = [TrajectoryStep(calls=[{"name": a.name, "arguments": deepcopy(a.arguments)}]) for a in actions]
    if comm:
        steps.append(TrajectoryStep(text=" ".join(comm)))
    return steps or [TrajectoryStep(text="How can I help?")]


def _table_id_field(domain: DomainDef, table_name: str) -> Optional[tuple[str, str]]:
    for t in domain.tables:
        if t.name == table_name and t.records:
            key = next((k for k in t.records[0] if k.endswith("_id") or k == "id"), None)
            if key:
                return t.name, key
    return None


def _other_value(domain: DomainDef, param: str, current: Any, rng: random.Random) -> Optional[Any]:
    stem = param[: -len("_id")] if param.endswith("_id") else None
    if stem is None:
        return None
    hit = _table_id_field(domain, stem if stem.endswith("s") else stem + "s")
    if hit is None:
        # try singular->plural variants already covered; give up
        return None
    tname, key = hit
    recs = next(t.records for t in domain.tables if t.name == tname)
    pool = [r[key] for r in recs if r[key] != current]
    return rng.choice(pool) if pool else None


def corrupt(
    variant: Variant,
    actions: list[ActionDef],
    communicate: list[str],
    domain: DomainDef,
    rng: random.Random,
) -> list[TrajectoryStep]:
    """Return the trajectory steps for one corrupted variant.

    `actions` are the golden actions (normalized). Not-applicable variants fall
    back to the correct baseline so every task contributes to every applicable
    class only.
    """
    if variant == Variant.CORRECT or not actions:
        return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))

    writes = [a for a in actions if is_write(a.name)]
    acts = deepcopy(actions)

    if variant == Variant.DROP_ACTION:
        if len(acts) < 2:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        victim = rng.choice(range(len(acts)))
        del acts[victim]
        return _steps_from(acts, communicate)

    if variant == Variant.WRONG_ARG_VALUE:
        idx = rng.randrange(len(acts))
        keys = [k for k in acts[idx].arguments if not k.endswith(("_id", "_ids"))]
        if not keys:
            keys = list(acts[idx].arguments.keys())
        if not keys:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        k = rng.choice(keys)
        v = acts[idx].arguments[k]
        acts[idx].arguments[k] = _mutate(v, rng)
        return _steps_from(acts, communicate)

    if variant == Variant.WRONG_ENTITY:
        cands = [i for i, a in enumerate(acts) for k in a.arguments if k.endswith("_id")]
        if not cands:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        idx = rng.choice(cands)
        idkeys = [k for k in acts[idx].arguments if k.endswith("_id")]
        k = rng.choice(idkeys)
        other = _other_value(domain, k, acts[idx].arguments[k], rng)
        if other is None:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        acts[idx].arguments[k] = other
        return _steps_from(acts, communicate)

    if variant == Variant.EXTRA_DESTRUCTIVE:
        wtools = [t for t in domain.tools if is_write(t.name)]
        if not wtools:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        td = rng.choice(wtools)
        args: dict[str, Any] = {}
        for p in td.params:
            if p.required:
                args[p.name] = _fill(p, domain, rng)
        return _steps_from(acts, communicate) + [TrajectoryStep(calls=[{"name": td.name, "arguments": args}])]
    if variant == Variant.BENIGN_EXTRA_READ:
        rtools = [t for t in domain.tools if t.name.startswith(("get_", "list_"))]
        if not rtools:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        td = rng.choice(rtools)
        args = {p.name: _fill(p, domain, rng) for p in td.params if p.required}
        return _steps_from(acts, communicate) + [TrajectoryStep(calls=[{"name": td.name, "arguments": args}])]

    if variant == Variant.REPEAT_WRITE:
        if not writes:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        dup = rng.choice(writes)
        return _steps_from(acts, communicate) + [
            TrajectoryStep(calls=[{"name": dup.name, "arguments": deepcopy(dup.arguments)}])
        ]

    if variant == Variant.SWAP_WRITES:
        idxs = [i for i, a in enumerate(acts) if is_write(a.name)]
        if len(idxs) < 2:
            return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))
        i, j = idxs[0], idxs[1]
        acts[i], acts[j] = acts[j], acts[i]
        return _steps_from(acts, communicate)

    return base_steps(TaskCriteria(actions=actions, communicate_info=communicate))


def _mutate(v: Any, rng: random.Random) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int):
        return v + 1
    if isinstance(v, float):
        return v + 0.5
    if isinstance(v, list):
        return [_mutate(x, rng) for x in v]
    s = str(v)
    if len(s) > 3:
        return s[:-1] + ("9" if s[-1] != "9" else "8")
    return s + "x"


def _fill(p, domain: DomainDef, rng: random.Random) -> Any:
    """Schema-valid AND executable filler: real ids from data, quoted example
    values from the param description, nested objects built from their schema.
    The corruption taxonomy promises an executable destructive write; junk that
    any real API would reject would silently turn the variant into a no-op."""
    if p.type == "array":
        if p.items_type == "object" and p.items_properties:
            one = {sp.name: _fill(sp, domain, rng) for sp in p.items_properties if sp.required or sp.name in ("flight_number", "payment_id", "amount", "date")}
            return [one]
        return [_fill_one_scalar(p.items_type or "string", p.name, domain, rng)]
    return _fill_one_scalar(p.type, p.name, domain, rng)


_QUOTED = re.compile(r"'([^']+)'")


def _quoted_example(p) -> Optional[str]:
    m = _QUOTED.search(p.description or "")
    return m.group(1) if m else None


def _identity_pool(domain: DomainDef, rng: random.Random, prefix_hint: str = ""):
    """Real identity values from the initial data."""
    pool = []
    for t in domain.tables:
        for rec in t.records[:50]:
            for k, v in rec.items():
                if isinstance(v, str) and (k.endswith("_id") or k == "id"):
                    pool.append(v)
                elif isinstance(v, dict):
                    pool.extend(kk for kk in v if isinstance(kk, str))
    return pool


def _fill_one_scalar(ptype: str, name: str, domain: DomainDef, rng: random.Random) -> Any:
    existing = _other_value(domain, name, object(), rng) if name.endswith("_id") else None
    if existing is not None:
        return existing
    q = _quoted_example(_param_hints.get(name)) if _param_hints and name in _param_hints else None
    if q is not None:
        return q
    if ptype == "integer":
        return rng.randrange(3)
    if ptype == "number":
        return 50.0
    if ptype == "boolean":
        return False
    # enum-ish or free string: fall back to a plain single word (never
    # ref-shaped, so neither our world nor a real API treats it as a reference)
    return "standard"


_param_hints: dict = {}


def load_param_hints(domain: DomainDef) -> None:
    """Index param descriptions once so fillers can use documented examples."""
    global _param_hints
    for t in domain.tools:
        for p in t.params:
            _param_hints.setdefault(p.name, p)
