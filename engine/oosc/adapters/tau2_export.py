"""tau2-bench export adapter.

Reads a tau2 domain through its public, read-only introspection APIs and
produces a normalized :class:`DomainDef` plus normalized tasks.

Boundary note (DECISIONS.md D2): this adapter is *harness plumbing* for
building test inputs and gold labels. The world derivation itself consumes
only the exported schemas. Nothing in ``oosc.world`` imports this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oosc.schema import ActionDef, DomainDef, ParamDef, TableDef, TaskCriteria, ToolDef


def _json_schema_to_params(schema: dict[str, Any] | None) -> list[ParamDef]:
    if not schema:
        return []
    required = set(schema.get("required", []))
    out: list[ParamDef] = []
    for name, spec in schema.get("properties", {}).items():
        t = spec.get("type", "string")
        items_type = None
        items_props = None
        if t == "array":
            items = spec.get("items") or {}
            items_type = items.get("type", "string")
            if items_type == "object" and items.get("properties"):
                items_props = _json_schema_to_params(items)
        out.append(
            ParamDef(
                name=name,
                type=t,
                description=spec.get("description", "") or "",
                required=name in required,
                items_type=items_type,
                items_properties=items_props,
            )
        )
    return out


def _db_tables(db_obj: Any) -> list[TableDef]:
    """Extract tables from a tau2 DB object.

    tau2 DBs are pydantic models whose fields are tables (dict[str, Record]
    or list[Record]). We treat every model field holding a record collection
    as a table and dump its records as plain JSON-safe dicts.
    """
    data = getattr(db_obj, "model_dump", None)
    raw = db_obj.model_dump() if callable(data) else dict(db_obj)
    tables = []
    for name, value in (raw or {}).items():
        if isinstance(value, dict):
            recs = [_to_plain(r) for r in value.values()]
        elif isinstance(value, list):
            recs = [_to_plain(r) for r in value]
        else:
            continue  # scalar metadata, not a table
        # keep only collections of records (dicts), skip scalar lists
        recs = [r for r in recs if isinstance(r, dict)]
        if not recs:
            continue
        tables.append(TableDef(name=str(name), records=recs))
    return tables


def _to_plain(obj: Any) -> Any:
    """pydantic models / nested containers -> plain JSON-safe python."""
    if hasattr(obj, "model_dump"):
        return _to_plain(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    return obj


def export_domain(domain_name: str) -> DomainDef:
    """Export one tau2 domain into our normalized schema."""
    from tau2.registry import registry  # local import: adapter boundary

    env = registry.get_env_constructor(domain_name)()
    tools = [
        ToolDef(
            name=t.name,
            short_desc=getattr(t, "short_desc", "") or "",
            long_desc=getattr(t, "long_desc", "") or "",
            params=_json_schema_to_params(t.params.model_json_schema()),
            requestor="assistant",
        )
        for t in (env.get_tools() or [])
    ]
    user_tools = env.user_tools or []
    for t in user_tools:
        tools.append(
            ToolDef(
                name=t.name,
                short_desc=getattr(t, "short_desc", "") or "",
                long_desc=getattr(t, "long_desc", "") or "",
                params=_json_schema_to_params(t.params.model_json_schema()),
                requestor="user",
            )
        )
    return DomainDef(
        name=domain_name,
        policy=env.policy or "",
        tools=tools,
        tables=_db_tables(env.tools.db),
    )


def export_tasks(domain_name: str) -> list[dict[str, Any]]:
    """Load a tau2 task set and normalize to our criteria shape."""
    from tau2.registry import registry
    from tau2.data_model.tasks import Task  # noqa: F401  (validation via registry)

    tasks = registry.get_tasks_loader(domain_name)()
    out = []
    for t in tasks:
        crit = t.evaluation_criteria
        actions = []
        if crit and crit.actions:
            for a in crit.actions:
                actions.append(
                    ActionDef(
                        action_id=a.action_id,
                        name=a.name,
                        arguments=dict(a.arguments or {}),
                        requestor=a.requestor,
                        compare_args=list(a.compare_args) if a.compare_args else None,
                    ).model_dump()
                )
        comm = list(crit.communicate_info or []) if crit else []
        basis = [str(x.value if hasattr(x, "value") else x) for x in (crit.reward_basis or [])] if crit else ["DB"]
        nl = (crit.nl_assertions or []) if crit else []
        out.append(
            {
                "id": t.id,
                "domain": domain_name,
                "user_scenario": _to_plain(t.user_scenario.model_dump()) if t.user_scenario else None,
                "criteria": {
                    "actions": actions,
                    "communicate_info": comm,
                    "reward_basis": basis,
                    "nl_assertions": _to_plain(nl),
                },
            }
        )
    return out


def write_export(domain_name: str, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dom_path = out_dir / f"{domain_name}.domain.json"
    task_path = out_dir / f"{domain_name}.tasks.json"
    dom_path.write_text(export_domain(domain_name).model_dump_json(indent=1), encoding="utf-8")
    task_path.write_text(json.dumps(export_tasks(domain_name), indent=1), encoding="utf-8")
    return dom_path, task_path
