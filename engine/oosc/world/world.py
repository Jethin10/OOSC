"""Runtime mock world executing schema-derived effect specs.

State = initial records + an ordered ledger of applied effects. The ledger -
not a reconstructed domain database - is the canonical state, because the
derivation intentionally knows nothing about domain-specific field semantics.
Equivalence of two trajectories is therefore *ledger equivalence after shadow
compression*: two writes on the same entities by the same tool collapse when
the later one subsumes the earlier (later-writer-wins), mirroring how a real
record update overwrites fields.

Every call appends structured events so runs replay deterministically and
failure classifiers can reason about exact state deltas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from oosc.world.derive import EffectKind, EffectSpec, WorldSpec

_PRIMITIVES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}

# Values that syntactically look like entity identifiers (#W123, credit_card_8897086,
# gen_cabin). Used ONLY to decide whether an unresolvable reference-looking argument
# should veto a write - plain words (economy), zips (80279), dates, emails and free
# text never trigger the check.
import re as _re

_REF_LIKE = _re.compile(r"^(#[A-Za-z]\w*|\w+_\w+)$")
_REF_KEYS = ("_id", "_ids", "_number", "_numbers", "payment_id")


def _canon(obj: Any) -> Any:
    """Canonical, order-stable JSON value for hashing."""
    if isinstance(obj, dict):
        return {k: _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_canon(x) for x in obj]
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    return obj


@dataclass
class CallResult:
    tool: str
    ok: bool
    error: Optional[str] = None
    mutated: bool = False
    bindings: list[dict] = field(default_factory=list)


@dataclass
class LedgerEntry:
    seq: int
    tool: str
    args: dict[str, Any]
    bindings: list[dict]  # [{param, table, key, path}]
    target_status: Optional[str] = None


@dataclass
class WorldEvent:
    seq: int
    kind: str  # call | read | mutate | error
    tool: str
    detail: dict[str, Any] = field(default_factory=dict)


class MockWorld:
    def __init__(self, spec: WorldSpec):
        self.spec = spec
        self.tables: dict[str, list[dict]] = {
            name: json.loads(json.dumps(t.records)) for name, t in spec.tables.items()
        }
        self.ledger: list[LedgerEntry] = []
        self.events: list[WorldEvent] = []
        self._transitions: set[tuple] = set()  # {(table,key,verb_family)}
        self._payments: dict[str, float] = {}  # payment_id -> spent so far
        self._seq = 0
        self._identities = self._collect_identities()
        self.initial_digest = hashlib.sha256(
            json.dumps(_canon(self.tables), sort_keys=True).encode()
        ).hexdigest()

    def _collect_identities(self) -> set[str]:
        """Every string that names an entity somewhere in the initial data:
        values at identity fields plus keys of embedded keyed collections."""
        out: set[str] = set()

        def walk(rec: dict):
            for k, v in rec.items():
                if k == "id" or k.endswith(("_id", "_ids", "_number", "_numbers")):
                    vals = v if isinstance(v, list) else [v]
                    for x in vals:
                        if isinstance(x, str):
                            out.add(x)
                if isinstance(v, dict):
                    out.update(k2 for k2 in v if isinstance(k2, str))
                    for el in v.values():
                        if isinstance(el, dict):
                            walk(el)
                elif isinstance(v, list):
                    for el in v:
                        if isinstance(el, dict):
                            walk(el)

        for recs in self.tables.values():
            for rec in recs:
                if isinstance(rec, dict):
                    walk(rec)
        return out

    # ---------------- entity resolution -----------------

    def _iter_records(self):
        """Yield (table, index, record) for top-level records."""
        for tname, recs in self.tables.items():
            for i, rec in enumerate(recs):
                yield tname, i, rec

    def _id_fields(self, rec: dict) -> list[str]:
        return [k for k in rec if k == "id" or k.endswith("_id") or k.endswith("_ids")]

    def resolve(self, param: str, value: Any, many: bool, table_hint: Optional[str]) -> list[dict]:
        """Find entities whose identity equals `value`.

        Identity match is structural: any top-level record with an id-ish field
        equal to the value, or any nested element under such a record's lists.
        Returns binding dicts {param, table, key(record index or id value), path}.
        """
        out: list[dict] = []
        want = str(value)

        def scan(rec: dict, path: str, table: str, idx: int):
            for f in self._id_fields(rec):
                v = rec[f]
                vals = v if isinstance(v, list) else [v]
                for item in vals:
                    if str(item) == want:
                        out.append({"param": param, "table": table, "key": idx, "path": f"{path}.{f}" if path else f})
            for f, v in rec.items():
                if isinstance(v, list):
                    for j, el in enumerate(v):
                        if isinstance(el, dict):
                            scan(el, f"{path}.{f}[{j}]" if path else f"{f}[{j}]", table, idx)
                elif isinstance(v, dict):
                    # embedded keyed collections (e.g. payment_methods): the
                    # mapping key itself can be an identity, and values are
                    # records that may carry their own id fields
                    if want in v:
                        out.append({"param": param, "table": table, "key": idx, "path": f"{path}.{f}.{want}" if path else f"{f}.{want}"})
                    for k2, el in v.items():
                        if isinstance(el, dict):
                            scan(el, f"{path}.{f}.{k2}" if path else f"{f}.{k2}", table, idx)

        tables = [table_hint] if table_hint else list(self.tables.keys())
        # hint first; if it yields nothing, fall back to full scan
        for t in tables:
            if t in self.tables:
                pass
        for tname, idx, rec in list(self._iter_records()):
            if table_hint and tname != table_hint:
                continue
            scan(rec, "", tname, idx)
        if not out and table_hint:
            for tname, idx, rec in self._iter_records():
                scan(rec, "", tname, idx)
        seen = set()
        uniq = []
        for b in out:
            k = json.dumps(_canon(b), sort_keys=True)
            if k not in seen:
                seen.add(k)
                uniq.append(b)
        if many:
            return uniq
        return uniq[:1]

    # ---------------- validation -----------------

    @staticmethod
    def validate_args(spec_tool_params, args: dict) -> Optional[str]:
        by_name = {p.name: p for p in spec_tool_params}
        for p in spec_tool_params:
            if p.required and p.name not in args:
                return f"missing required argument '{p.name}'"
        for k, v in args.items():
            p = by_name.get(k)
            if p is None:
                continue  # unknown extra args are tolerated like most real APIs
            t = p.type
            if t in _PRIMITIVES and not isinstance(v, bool) and not isinstance(v, _PRIMITIVES[t]):
                # tolerate int-for-number only
                if not (t == "number" and isinstance(v, int)):
                    return f"argument '{k}' expected {t}, got {type(v).__name__}"
            if t == "array" and not isinstance(v, list):
                return f"argument '{k}' expected array"
        return None

    # ---------------- execution -----------------

    def call(self, tool_name: str, args: dict[str, Any]) -> CallResult:
        self._seq += 1
        seq = self._seq
        tool = self.spec.domain.tool(tool_name)
        eff = self.spec.effects.get(tool_name)
        if eff is None or tool is None:
            self.events.append(WorldEvent(seq, "error", tool_name, {"error": "unknown tool"}))
            return CallResult(tool=tool_name, ok=False, error="unknown tool")

        if eff.kind in (EffectKind.READ, EffectKind.TERMINAL):
            self.events.append(WorldEvent(seq, "read", tool_name, {"args": _canon(args)}))
            return CallResult(tool=tool_name, ok=True, mutated=False)

        err = self.validate_args(tool.params, args)
        if err:
            self.events.append(WorldEvent(seq, "error", tool_name, {"error": err}))
            return CallResult(tool=tool_name, ok=False, error=err)

        # bind entities
        bindings: list[dict] = []
        for b in eff.bindings:
            val = args.get(b.param)
            if b.many:
                found: list[dict] = []
                for v in val or []:
                    found.extend(self.resolve(b.param, v, False, b.table_hint))
            else:
                found = self.resolve(b.param, val, False, b.table_hint) if val is not None else []
            if val is not None and not found:
                self.events.append(
                    WorldEvent(seq, "error", tool_name, {"error": f"unresolved entity '{b.param}'={val!r}"})
                )
                return CallResult(tool=tool_name, ok=False, error=f"unresolved entity {b.param}")
            bindings.extend(found)

        veto = self._payload_veto(tool, args)
        if veto:
            self.events.append(WorldEvent(seq, "error", tool_name, {"error": veto}))
            return CallResult(tool=tool_name, ok=False, error=veto)

        primary = self._primary_entity(bindings, eff)
        if primary is not None and eff.kind == EffectKind.WRITE:
            veto = self._lifecycle_veto(eff, primary)
            if veto:
                self.events.append(WorldEvent(seq, "error", tool_name, {"error": veto}))
                return CallResult(tool=tool_name, ok=False, error=veto)

        entry = LedgerEntry(
            seq=seq,
            tool=tool_name,
            args=json.loads(json.dumps(_canon(args))),
            bindings=[{k: b[k] for k in ("param", "table", "key", "path")} for b in bindings],
            target_status=eff.target_status,
        )
        veto = self._balance_veto(tool_name, args)
        if veto:
            self.events.append(WorldEvent(seq, "error", tool_name, {"error": veto}))
            return CallResult(tool=tool_name, ok=False, error=veto)
        self.ledger.append(entry)
        if eff.target_status and primary is not None:
            self._write_status(primary, eff.target_status)
            fam = self._verb_family(tool_name)
            self._transitions.add((primary["table"], primary["key"], fam))
        self.events.append(
            WorldEvent(seq, "mutate", tool_name, {"bindings": entry.bindings, "args": entry.args})
        )
        return CallResult(tool=tool_name, ok=True, mutated=True, bindings=entry.bindings)

    # ---------------- payload semantics -----------------

    def _payload_veto(self, tool, args: dict) -> Optional[str]:
        """Generic reference-integrity checks derived from schema + data.

        1. Array params whose declared items are objects reject scalar junk.
        2. Reference-looking values under reference-named keys must exist in
           the initial data (unknown id-shaped values are rejected), UNLESS the
           value is a documented example in the param description ('round_trip').
        3. Duplicate references inside one *_ids array are rejected - real
           APIs refuse to process the same entity twice in one call.
        """
        eff = self.spec.effects.get(tool.name)
        allowed = eff.param_allowed if eff else {}
        for p in tool.params:
            v = args.get(p.name)
            if v is None:
                continue
            ok_vals = allowed.get(p.name, set())
            if p.type == "array" and p.items_type == "object" and isinstance(v, list):
                if any(not isinstance(x, dict) for x in v):
                    return f"{p.name}: expected objects"
            key_is_ref = p.name.endswith(_REF_KEYS) or p.name in ("id",)
            scalars: list[str] = []
            if isinstance(v, str):
                scalars = [v]
            elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                scalars = list(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        for k2, v2 in x.items():
                            if k2.endswith(_REF_KEYS) and isinstance(v2, str):
                                scalars.append(v2)
            for s in scalars:
                if s.lower() in ok_vals:
                    continue
                if key_is_ref or _REF_LIKE.match(s):
                    if s not in self._identities:
                        return f"{p.name}: unknown reference '{s}'"
            if p.name.endswith("_ids") and isinstance(v, list) and len(set(map(str, v))) != len(v):
                return f"{p.name}: duplicate references"
        return None

    def _balance_veto(self, tool_name: str, args: dict) -> Optional[str]:
        """Resource-capacity rule inferred from field names: payment entries
        ({payment_id, amount}) may not spend past the payment method's stored
        balance. Mirrors how real APIs decline over-spending instruments."""
        spends: list[tuple[str, float]] = []
        for k, v in args.items():
            entries = v if isinstance(v, list) else [v]
            for e in entries:
                if isinstance(e, dict) and "payment_id" in e and isinstance(e.get("amount"), (int, float)):
                    spends.append((str(e["payment_id"]), float(e["amount"])))
                elif isinstance(e, dict) and "payment_id" in e and "amount" not in e:
                    pass
        single = args.get("payment_id")
        if isinstance(single, str) and "amount" in args and isinstance(args["amount"], (int, float)):
            spends.append((single, float(args["amount"])))
        for pid, amount in spends:
            bal = self._balance_of(pid)
            if bal is None:
                continue
            spent = self._payments.get(pid, 0.0)
            if spent + amount > bal + 1e-9:
                return f"payment '{pid}': insufficient balance"
        for pid, amount in spends:
            self._payments[pid] = self._payments.get(pid, 0.0) + amount
        return None

    def _balance_of(self, pid: str) -> Optional[float]:
        for recs in self.tables.values():
            for rec in recs:
                for f, v in rec.items():
                    if isinstance(v, dict) and pid in v:
                        b = v[pid].get("balance")
                        if isinstance(b, (int, float)):
                            return float(b)
        return None

    # ---------------- lifecycle -----------------

    @staticmethod
    def _verb_family(tool_name: str) -> str:
        for verb in ("cancel", "return", "exchange", "refund", "book"):
            if verb in tool_name:
                return verb
        return tool_name

    def _primary_entity(self, bindings: list[dict], eff: EffectSpec) -> Optional[dict]:
        """The single bound entity that carries a status field, if any."""
        for b in bindings:
            if b["path"].endswith(("status",)):
                continue
            if b["many"] if "many" in b else False:
                continue
            recs = self.tables.get(b["table"])
            if recs is None:
                continue
            rec = recs[b["key"]] if isinstance(b["key"], int) and 0 <= b["key"] < len(recs) else None
            if isinstance(rec, dict) and isinstance(rec.get("status"), str):
                return b
        return None

    def _status_of(self, b: dict) -> Optional[str]:
        recs = self.tables.get(b["table"])
        if not recs:
            return None
        rec = recs[b["key"]] if isinstance(b["key"], int) and 0 <= b["key"] < len(recs) else None
        if isinstance(rec, dict):
            s = rec.get("status")
            return s.lower() if isinstance(s, str) else None
        return None

    def _lifecycle_veto(self, eff: EffectSpec, primary: dict) -> Optional[str]:
        cur = self._status_of(primary)
        ident = (primary["table"], primary["key"], self._verb_family(eff.name))
        if eff.one_shot and ident in self._transitions:
            return f"{eff.name}: transition already applied to {primary['table']}[{primary['key']}]"
        if cur is not None:
            if eff.required_statuses and cur not in eff.required_statuses:
                return f"{eff.name}: status '{cur}' not in required {sorted(eff.required_statuses)}"
            if cur in eff.blocking_statuses:
                return f"{eff.name}: status '{cur}' is blocking"
        return None

    def _write_status(self, b: dict, status: str) -> None:
        recs = self.tables.get(b["table"])
        if recs and isinstance(b["key"], int) and 0 <= b["key"] < len(recs):
            recs[b["key"]]["status"] = status

    # ---------------- equivalence -----------------

    def compressed_ledger(self) -> list[dict]:
        """Shadow-compressed ledger.

        Within (tool, ordered entity-set) group: an earlier entry is dropped if
        some later entry binds a superset of its entities (later write wins).
        Read effects never enter the ledger, so pure reads are invisible to
        equivalence - matching real environments where reads don't change state.
        """
        entries = [
            {
                "tool": e.tool,
                "args": e.args,
                "group": (
                    e.tool,
                    tuple(sorted({(b["table"], str(b["key"])) for b in e.bindings})),
                ),
                "bindkeys": frozenset((b["table"], str(b["key"]), b["path"]) for b in e.bindings),
                "seq": e.seq,
                "compressible": self.spec.effects[e.tool].kind == EffectKind.WRITE,
            }
            for e in self.ledger
        ]
        kept: list[dict] = []
        for e in entries:
            if not e["compressible"]:
                kept.append(e)
                continue
            drop = False
            for k in kept:
                if (
                    k.get("compressible")
                    and k["group"][0] == e["group"][0]
                    and k["group"][1] == e["group"][1]
                    and e["bindkeys"] >= k["bindkeys"]
                ):
                    kept.remove(k)
                    break
            kept.append(e)
        out = [{"tool": e["tool"], "args": e["args"], "bind": sorted(list(e["bindkeys"]))} for e in kept]
        # Canonical ordering before hashing. Real environments compare FINAL
        # state, so independent effects are order-insensitive; order-dependent
        # cases already differ in CONTENT because lifecycle vetoes no-op the
        # conflicting call, changing which entries exist.
        out.sort(key=lambda x: (x["tool"], json.dumps(_canon(x["args"]), sort_keys=True), json.dumps(x["bind"])))
        return out

    def fingerprint(self) -> str:
        payload = {
            "initial": self.initial_digest,
            "effects": _canon(self.compressed_ledger()),
        }
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()

    def snapshot(self) -> dict:
        return {
            "fingerprint": self.fingerprint(),
            "mutations": len(self.ledger),
            "events": len(self.events),
        }

    def clone(self) -> "MockWorld":
        w = MockWorld(self.spec)
        w.tables = json.loads(json.dumps(self.tables))
        w.ledger = [LedgerEntry(**json.loads(json.dumps(e.__dict__))) for e in self.ledger]
        w.events = list(self.events)
        w._transitions = set(self._transitions)
        w._seq = self._seq
        return w
