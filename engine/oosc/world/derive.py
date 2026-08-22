"""Derive a stateful mock-world specification from tool schemas alone.

Input: :class:`oosc.schema.DomainDef` (names, descriptions, param JSON schemas,
initial DB records). Output: :class:`WorldSpec` - per-tool effect specifications
that the runtime world executes. No domain code is imported or executed here;
this module consumes plain data only (DECISIONS.md D2).

Derivation rules are GENERIC (domain-agnostic). They were written once against
public benchmark documentation, then frozen. See ``tests/test_derive.py``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from oosc.schema import DomainDef, ParamDef, TableDef, ToolDef


class EffectKind(str, Enum):
    READ = "read"          # never mutates state
    WRITE = "write"        # mutates state when preconditions hold
    CREATE = "create"      # adds a new entity (no identity binding)
    TERMINAL = "terminal"  # ends/hands off; never mutates state


_ID_SUFFIX = re.compile(r"_(ids?)$")
_READ_PREFIX = ("get_", "find_", "search_", "list_", "check_", "calculate")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_BLOCK_CUE = re.compile(r"\b(cannot|can not|can't|not be|already)\b", re.I)
_ONLY_CUE = re.compile(r"\bonly\b", re.I)
_TARGET_CUE = [
    re.compile(r"chang\w*\s+to\s+['\"]?(\w[\w-]*)['\"]?", re.I),
    re.compile(r"will\s+be\s+['\"]?(\w[\w-]*)['\"]?", re.I),
    re.compile(r"set\s+to\s+['\"]?(\w[\w-]*)['\"]?", re.I),
]
_VERB_TARGET = {
    "cancel": "cancelled",
    "return": "returned",
}
_ONE_SHOT_VERBS = {"cancel", "return", "exchange"}


def classify_kind(tool: ToolDef) -> EffectKind:
    n = tool.name
    if n.startswith(_READ_PREFIX):
        return EffectKind.READ
    if n.startswith("transfer_"):
        return EffectKind.TERMINAL
    if n.startswith(("book_", "add_", "create_")):
        # candidate creator; confirmed as CREATE only if no identity binding
        return EffectKind.CREATE
    return EffectKind.WRITE


def _stem(param_name: str) -> tuple[str, bool]:
    """Return (stem, is_many) for *_id / *_ids style params."""
    m = _ID_SUFFIX.search(param_name)
    if not m:
        return param_name, False
    many = m.group(1) == "ids"
    stem = param_name[: m.start()]
    return stem, many


def _singular(stem: str) -> str:
    return stem[:-1] if stem.endswith("s") else stem


def _match_table(stem: str, tables: list[TableDef]) -> Optional[str]:
    """Match an id-stem to a table by name (order->orders, user->users...)."""
    want_sing = _singular(stem)
    for t in tables:
        tname = t.name
        tsing = _singular(tname.rstrip("0123456789"))
        if tname == stem or tname == stem + "s" or tsing == want_sing:
            return t.name
    return None


@dataclass
class Binding:
    """A parameter that references an existing entity."""

    param: str
    many: bool
    table_hint: Optional[str] = None  # None => runtime value-scan only


@dataclass
class EffectSpec:
    """What a tool does to the world - inferred purely from its declaration."""

    name: str
    kind: EffectKind
    bindings: list[Binding] = field(default_factory=list)
    payload_params: list[str] = field(default_factory=list)
    required_statuses: set[str] = field(default_factory=set)
    blocking_statuses: set[str] = field(default_factory=set)
    target_status: Optional[str] = None
    one_shot: bool = False
    # documented example values per param (quoted strings in the description):
    # these are legal even when underscore-shaped like 'round_trip'
    param_allowed: dict[str, set[str]] = field(default_factory=dict)


class WorldSpec:
    """The complete derived world model."""

    def __init__(self, domain: DomainDef):
        self.domain = domain
        self.tables = {t.name: t for t in domain.tables}
        self.effects: dict[str, EffectSpec] = {}
        self.status_vocab = self._extract_status_vocab()
        for tool in domain.tools:
            self.effects[tool.name] = self._derive_effect(tool)

    # ---------------- derivation -----------------

    def _extract_status_vocab(self) -> dict[str, set[str]]:
        """Status vocabulary comes from the DATA, not from prose: every distinct
        value of a `status` field observed in the initial records."""
        vocab: dict[str, set[str]] = defaultdict(set)
        for t in self.domain.tables:
            for rec in t.records:
                s = rec.get("status") if isinstance(rec, dict) else None
                if isinstance(s, str):
                    vocab[t.name].add(s.lower())
                # nested statuses (e.g., flights inside reservations)
                if isinstance(rec, dict):
                    for v in rec.values():
                        if isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict) and isinstance(item.get("status"), str):
                                    vocab[t.name].add(item["status"].lower())
        return dict(vocab)

    def _derive_effect(self, tool: ToolDef) -> EffectSpec:
        kind = classify_kind(tool)
        bindings: list[Binding] = []
        payload: list[str] = []
        for p in tool.params:
            stem, many = _stem(p.name)
            if _ID_SUFFIX.search(p.name):
                hint = _match_table(stem, list(self.tables.values()))
                bindings.append(Binding(param=p.name, many=many, table_hint=hint))
            elif p.type == "array":
                payload.append(p.name)
            else:
                payload.append(p.name)
        eff = EffectSpec(
            name=tool.name,
            kind=kind,
            bindings=bindings,
            payload_params=[p.name for p in tool.params if p.name not in {b.param for b in bindings}],
        )
        eff.param_allowed = {
            p.name: {m.lower() for m in re.findall(r"'([^']+)'", p.description or "")}
            for p in tool.params
        }
        if kind == EffectKind.CREATE:
            # Creators add a NEW entity each call (e.g. book_reservation). They
            # bind existing entities (the owning user) but must never
            # shadow-compress against each other and are never one-shot.
            return eff
        if kind == EffectKind.WRITE:
            self._infer_preconditions_and_target(tool, eff)
        return eff

    def _candidate_status_tables(self, eff: EffectSpec) -> set[str]:
        tabs = {b.table_hint for b in eff.bindings if b.table_hint}
        return {t for t in tabs if self.status_vocab.get(t)}

    def _infer_preconditions_and_target(self, tool: ToolDef, eff: EffectSpec) -> None:
        desc = tool.full_desc
        if not desc:
            return
        vocabs = self._candidate_status_tables(eff)
        all_tokens: set[str] = set()
        for t in vocabs:
            all_tokens |= self.status_vocab[t]
        if not all_tokens:
            return
        short_sentences = [s for s in _SENT_SPLIT.split(tool.short_desc) if s]
        for sent in _SENT_SPLIT.split(desc):
            if not sent:
                continue
            low = sent.lower()
            hits = {tok for tok in all_tokens if re.search(rf"\b{re.escape(tok)}\b", low)}
            if not hits:
                continue
            if _ONLY_CUE.search(low) and re.search(r"\b(can|may)\b", low):
                eff.required_statuses |= hits  # "Only X can be ..."
            elif _BLOCK_CUE.search(low):
                eff.blocking_statuses |= hits  # "... cannot be cancelled"
            elif len(short_sentences) <= 2 and any(sent.strip() in s for s in short_sentences):
                eff.required_statuses |= hits  # opening sentence states scope
        # target status from explicit cues anywhere in the description
        joined = " . ".join(_SENT_SPLIT.split(desc))
        for cue in _TARGET_CUE:
            m = cue.search(joined)
            if m:
                tok = m.group(1).lower()
                if tok in all_tokens:
                    eff.target_status = tok
                    break
        if eff.target_status is None:
            for verb, tgt in _VERB_TARGET.items():
                if verb in tool.name and tgt in all_tokens:
                    eff.target_status = tgt
                    break
        eff.one_shot = (
            eff.kind == EffectKind.WRITE
            and (eff.target_status is not None or any(v in tool.name for v in _ONE_SHOT_VERBS))
        )

    # ---------------- reporting -----------------

    def summary(self) -> dict:
        out = {"domain": self.domain.name, "tables": {k: len(v.records) for k, v in self.tables.items()}, "effects": {}}
        for name, e in self.effects.items():
            out["effects"][name] = {
                "kind": e.kind.value,
                "bindings": [{"param": b.param, "table": b.table_hint, "many": b.many} for b in e.bindings],
                "required": sorted(e.required_statuses),
                "blocking": sorted(e.blocking_statuses),
                "target": e.target_status,
                "one_shot": e.one_shot,
            }
        return out
