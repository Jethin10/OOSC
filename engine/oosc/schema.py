"""Normalized, JSON-safe schema types.

These are the ONLY inputs the world derivation may consume (see DECISIONS.md D2).
Every field is plain data: names, descriptions, JSON schemas, DB records.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ParamDef(BaseModel):
    """One tool parameter, flattened from its JSON schema."""

    name: str
    type: str = "string"  # json-schema primitive: string|integer|number|boolean|array|object|null
    description: str = ""
    required: bool = False
    items_type: Optional[str] = None  # for arrays
    items_properties: Optional[list["ParamDef"]] = None  # for arrays of objects


class ToolDef(BaseModel):
    """A tool as declared by its schema. No behavior, only declaration."""

    name: str
    short_desc: str = ""
    long_desc: str = ""
    params: list[ParamDef] = Field(default_factory=list)
    requestor: Literal["assistant", "user", "either"] = "either"

    @property
    def full_desc(self) -> str:
        return f"{self.short_desc} {self.long_desc}".strip()


class TableDef(BaseModel):
    """One table of the initial world state."""

    name: str
    records: list[dict[str, Any]] = Field(default_factory=list)


class DomainDef(BaseModel):
    """Everything the engine knows about a domain - schemas and state only."""

    name: str
    policy: str = ""
    tools: list[ToolDef] = Field(default_factory=list)
    tables: list[TableDef] = Field(default_factory=list)

    def tool(self, name: str) -> Optional[ToolDef]:
        return next((t for t in self.tools if t.name == name), None)


class ActionDef(BaseModel):
    """An expected (golden) action inside a task's evaluation criteria."""

    action_id: Optional[str] = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    requestor: Literal["assistant", "user"] = "assistant"
    compare_args: Optional[list[str]] = None


class TaskCriteria(BaseModel):
    """Evaluation criteria, normalized across benchmarks."""

    actions: list[ActionDef] = Field(default_factory=list)
    communicate_info: list[str] = Field(default_factory=list)
    reward_basis: list[str] = Field(
        default_factory=lambda: ["DB", "ACTION"]
    )  # subset of DB|ACTION|COMMUNICATE|NL_ASSERTION


class Scenario(BaseModel):
    """A generated or imported test scenario."""

    id: str
    domain: str
    category: str = "realistic"  # realistic | adversarial:<kind>
    instructions: str = ""
    initial_db_override: dict[str, Any] = Field(default_factory=dict)
    criteria: TaskCriteria = Field(default_factory=TaskCriteria)
    meta: dict[str, Any] = Field(default_factory=dict)
