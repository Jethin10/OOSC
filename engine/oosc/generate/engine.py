"""Scenario generation from schemas + initial data alone (no task files).

The generator enumerates data-grounded operations: for every entity in the
initial world it proposes the writes the domain's tools make possible, with
payloads drawn from the data itself (real ids, variants of the same product,
the user's own payment methods, documented example values). Discovery read
chains are emitted in plausible route variants. Everything is seeded.

Two outputs:
- ``generate()``: bounded Scenario objects for sandbox runs / platform use.
- ``enumerate_digests()``: exact action-sequence signature digests at full
  payload breadth, used for rediscovery matching (same frozen definition as
  D9 - complete canonical argument equality - just hashed for scale).

The generator never reads any benchmark task file (import-lint test).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from oosc.schema import ActionDef, DomainDef, TaskCriteria
from oosc.world.derive import WorldSpec


@dataclass
class Op:
    """One candidate operation over concrete entities."""

    name: str
    args: dict[str, Any]
    reads: list[tuple[str, dict[str, Any]]]  # discovery chain before the write
    instruction: str


def _quoted_values(text: str) -> list[str]:
    return re.findall(r"'([^']+)'", text or "")


def actions_digest(actions: list[tuple[str, dict]]) -> str:
    blob = json.dumps(
        [(n, json.dumps(a, sort_keys=True, default=str)) for n, a in actions],
        default=str,
    ).encode()
    return hashlib.sha1(blob).hexdigest()


def _primary_entity(op: Op) -> Optional[str]:
    for k, v in op.args.items():
        if k.endswith("_id") and isinstance(v, str):
            return v
    return None


class WorldIndex:
    """Entity relationships extracted from the initial records."""

    def __init__(self, domain: DomainDef):
        self.domain = domain
        self.tables = {t.name: t.records for t in domain.tables}
        self.users: list[dict] = []
        self.orders_by_user: dict[str, list[dict]] = {}
        self.reservations_by_user: dict[str, list[dict]] = {}
        self.products: list[dict] = self.tables.get("products", [])
        self.product_by_id = {str(p.get("product_id")): p for p in self.products}
        self.flights: list[dict] = self.tables.get("flights", [])
        user_table = None
        for name, recs in self.tables.items():
            if not (recs and isinstance(recs[0], dict)):
                continue
            keys = set(recs[0].keys())
            if name == "orders":
                for o in recs:
                    self.orders_by_user.setdefault(str(o.get("user_id")), []).append(o)
            elif name == "reservations":
                for r in recs:
                    self.reservations_by_user.setdefault(str(r.get("user_id")), []).append(r)
            elif "email" in keys and "name" in keys:
                user_table = recs
        self.users = user_table or []

    def user(self, uid: str) -> Optional[dict]:
        return next((u for u in self.users if str(u.get("user_id")) == uid), None)


class ScenarioGenerator:
    def __init__(self, domain: DomainDef, seed: int = 7, budget: int = 120000):
        self.domain = domain
        self.spec = WorldSpec(domain)
        self.index = WorldIndex(domain)
        self.rng = random.Random(seed)
        self.budget = budget
        self.tool_names = {t.name for t in domain.tools}

    # ---------- helpers ----------

    @staticmethod
    def _payment_options(user: dict) -> list[str]:
        pm = user.get("payment_methods") or {}
        return [k for k in pm.keys() if isinstance(k, str)]

    def _variant_alternatives(self, product_id: str, variant_id: str) -> list[str]:
        """Available variants of the same product differing in options."""
        p = self.index.product_by_id.get(str(product_id))
        if not p:
            return []
        variants = p.get("variants") or {}
        base_key = next(
            (k for k, v in variants.items() if str(v.get("item_id")) == str(variant_id) or k == str(variant_id)),
            None,
        )
        if base_key is None:
            return []
        base = variants[base_key]
        alts = []
        for k, v in variants.items():
            vid = str(v.get("item_id") or k)
            if vid == str(variant_id) or not v.get("available", True):
                continue
            if v.get("options") != base.get("options"):
                alts.append(vid)
        return alts

    def _route_reads(self, user: dict, order_id: str) -> list[list[tuple[str, dict]]]:
        """Discovery chains: both identity routes, optionally with
        get_user_details after lookup."""
        name = user.get("name") or {}
        base_a = [
            ("find_user_id_by_name_zip", {"first_name": name.get("first_name"), "last_name": name.get("last_name"), "zip": (user.get("address") or {}).get("zip")}),
            ("get_order_details", {"order_id": order_id}),
        ]
        base_b = [
            ("find_user_id_by_email", {"email": user.get("email")}),
            ("get_order_details", {"order_id": order_id}),
        ]
        with_user = [("get_user_details", {"user_id": user.get("user_id")})]
        routes = []
        for b in (base_a, base_b):
            if not all(n in self.tool_names for n, _ in b):
                continue
            routes.append(b)
            routes.append([b[0]] + with_user + b[1:])
        return routes

    def _product_read_variants(
        self, route: list[tuple[str, dict]], items: list[dict], allow_empty: bool = False
    ) -> list[list[tuple[str, dict]]]:
        """Chain variants: product reads inserted or omitted; optionally no
        discovery reads at all (authors omit them when the persona knows ids)."""
        prods = []
        seen = set()
        for it in items:
            pid = str(it.get("product_id"))
            if pid not in seen and "get_product_details" in self.tool_names:
                seen.add(pid)
                prods.append(("get_product_details", {"product_id": pid}))
        out = [route]
        if prods:
            out.append(route + prods)
        if allow_empty:
            out.insert(0, [])
        return {json.dumps(r, default=str): r for r in out}.values()

    def _item_subsets_for_match(self, ids: list) -> list[list]:
        """Subsets worth enumerating for matching: singles, every pair,
        triples (capped), and the full set."""
        out = [[i] for i in ids]
        n = len(ids)
        for i in range(n):
            for j in range(i + 1, n):
                out.append([ids[i], ids[j]])
        import itertools

        for tri in itertools.islice(itertools.combinations(ids, 3), 6):
            out.append(list(tri))
        if 1 < n <= 5:
            out.append(list(ids))
        dedup = {tuple(x): x for x in out}
        return list(dedup.values())

    def _subsets(self, ids: list, max_n: int = 4) -> list[list]:
        """Non-empty prefix subsets up to a cap (platform-mode sampler)."""
        out = [[i] for i in ids]
        n = len(ids)
        for size in range(2, n + 1):
            out.append(ids[:size])
            if len(out) >= max_n:
                break
        return out[:max_n]

    @staticmethod
    def _cross(alt_lists: list[list[str]], cap: int) -> list[list[str]]:
        combos = [[]]
        for alts in alt_lists:
            combos = [c + [a] for c in combos for a in alts]
            if len(combos) > cap:
                break
        return combos[:cap]

    # ---------- op enumeration ----------

    def ops_for_order(
        self,
        user: dict,
        order: dict,
        rng: random.Random,
        breadth: bool = False,
    ) -> list[Op]:
        ops: list[Op] = []
        oid = order.get("order_id")
        status = str(order.get("status", ""))
        items = order.get("items") or []
        pays = self._payment_options(user)
        routes = self._route_reads(user, oid)
        if not routes:
            return ops

        def emit(tool: str, args: dict, relevant_items: list[dict], instruction: str):
            ref_ids = set()
            for v in args.values():
                if isinstance(v, list):
                    ref_ids.update(str(x) for x in v)
            rel = [it for it in relevant_items if str(it.get("item_id")) in ref_ids] or relevant_items
            # product-read sets: referenced products alone, plus variants with
            # ONE extra product from the same order (authors read alternates)
            gp = "get_product_details" in self.tool_names
            ref_pids, other_pids, seenp = [], [], set()
            for it in rel:
                pid = str(it.get("product_id"))
                if pid not in seenp:
                    seenp.add(pid)
                    ref_pids.append(pid)
            for it in relevant_items:
                pid = str(it.get("product_id"))
                if pid not in seenp:
                    seenp.add(pid)
                    other_pids.append(pid)
            prod_sets = [[]]
            if gp and ref_pids:
                prod_sets.append(list(ref_pids))
                for extra in other_pids[:2]:
                    prod_sets.append(ref_pids + [extra])
                    prod_sets.append([extra] + ref_pids)
            elif gp and other_pids:
                prod_sets.append(list(other_pids[:1]))
            for route in routes:
                for pl in prod_sets:
                    chain = route + [("get_product_details", {"product_id": p}) for p in pl]
                    ops.append(Op(tool, args, chain, instruction))

        if status == "pending":
            if "cancel_pending_order" in self.tool_names:
                for reason in ["no longer needed", "ordered by mistake"]:
                    emit(
                        "cancel_pending_order",
                        {"order_id": oid, "reason": reason},
                        items,
                        f"Cancel my order {oid} - {reason}.",
                    )
            addr = order.get("address") or {}
            if "modify_pending_order_address" in self.tool_names and addr:
                preview = " ".join(str(x) for x in list(addr.values())[:3])
                args = {"order_id": oid}
                args.update({k: v for k, v in addr.items() if k in {"address1", "address2", "city", "state", "country", "zip"}})
                emit("modify_pending_order_address", args, items, f"Update the address on order {oid} to {preview}.")
            if "modify_pending_order_items" in self.tool_names and items and pays:
                exchable = [it for it in items if self._variant_alternatives(it.get("product_id"), it.get("item_id"))]
                subs = (
                    self._item_subsets_for_match([it.get("item_id") for it in exchable])
                    if breadth
                    else self._subsets([it.get("item_id") for it in exchable], 3)
                ) if exchable else []
                by_id = {str(it.get("item_id")): it for it in exchable}
                cap = 60 if breadth else 36
                for sub in subs:
                    alt_lists = [
                        self._variant_alternatives(by_id[str(i)].get("product_id"), i)[:14]
                        for i in sub
                        if str(i) in by_id
                    ]
                    if not alt_lists or any(not a for a in alt_lists):
                        continue
                    for new_items in self._cross(alt_lists, cap):
                        for pay in pays[:4]:
                            emit(
                                "modify_pending_order_items",
                                {"order_id": oid, "item_ids": list(sub), "new_item_ids": new_items, "payment_method_id": pay},
                                items,
                                f"Exchange items {list(sub)} in order {oid} for variants {new_items}, pay difference with {pay}.",
                            )
            if "modify_pending_order_payment" in self.tool_names and len(pays) > 1:
                for pay in pays[:4]:
                    emit("modify_pending_order_payment", {"order_id": oid, "payment_method_id": pay}, items, f"Switch payment on order {oid} to {pay}.")
        if status == "delivered":
            item_ids = [it.get("item_id") for it in items]
            if "return_delivered_order_items" in self.tool_names:
                sub_source = self._item_subsets_for_match(item_ids) if breadth else self._subsets(item_ids, 3)
                for sub in sub_source:
                    for pay in pays[:4]:
                        emit(
                            "return_delivered_order_items",
                            {"order_id": oid, "item_ids": sub, "payment_method_id": pay},
                            items,
                            f"Return items {sub} from order {oid}, refund to {pay}.",
                        )
            if "exchange_delivered_order_items" in self.tool_names and items:
                exchable = [it for it in items if self._variant_alternatives(it.get("product_id"), it.get("item_id"))]
                subs = (
                    self._item_subsets_for_match([it.get("item_id") for it in exchable])
                    if breadth
                    else self._subsets([it.get("item_id") for it in exchable], 3)
                ) if exchable else []
                by_id = {str(it.get("item_id")): it for it in exchable}
                cap = 60 if breadth else 36
                for sub in subs:
                    alt_lists = [
                        self._variant_alternatives(by_id[str(i)].get("product_id"), i)[:14]
                        for i in sub
                        if str(i) in by_id
                    ]
                    if not alt_lists or any(not a for a in alt_lists):
                        continue
                    for new_items in self._cross(alt_lists, cap):
                        for pay in pays[:4]:
                            emit(
                                "exchange_delivered_order_items",
                                {"order_id": oid, "item_ids": list(sub), "new_item_ids": new_items, "payment_method_id": pay},
                                items,
                                f"Exchange {list(sub)} for {new_items} in order {oid}, pay difference with {pay}.",
                            )
        return ops

    def ops_for_user_address(self, user: dict, rng: random.Random) -> list[Op]:
        if "modify_user_address" not in self.tool_names:
            return []
        addr = user.get("address") or {}
        if not addr:
            return []
        args = {"user_id": user.get("user_id")}
        args.update(dict(addr))
        return [Op("modify_user_address", args, [], f"Update my address on file to {addr.get('address1')}, {addr.get('city')}.")]

    # ---------- read-only scenario family ----------

    def ops_readonly(self, user: dict, rng: random.Random) -> list[Op]:
        """Information-seeking operations grounded in data: searches over real
        airports/dates, status lookups, detail pulls. Many hand-authored tasks
        are pure information requests with no writes at all."""
        ops: list[Op] = []
        uid = user.get("user_id")
        name = user.get("name") or {}
        routes = self._route_reads_for_airline(user)
        resv = self.index.reservations_by_user.get(uid, [])

        def emit(chain: list[tuple[str, dict]], instruction: str):
            ops.append(Op("__readonly__", {}, chain, instruction))

        if "get_user_details" in self.tool_names:
            emit([("get_user_details", {"user_id": uid})], f"What address do you have on file for me?")
        for r in resv[:2]:
            rid = r.get("reservation_id")
            chain = []
            if "get_user_details" in self.tool_names:
                chain.append(("get_user_details", {"user_id": uid}))
            if "get_reservation_details" in self.tool_names:
                chain.append(("get_reservation_details", {"reservation_id": rid}))
            if len(chain) >= 2:
                emit(chain, f"What are the details of my reservation {rid}?")
            # flights in this reservation: status lookups
            for f in (r.get("flights") or [])[:2]:
                fn = (f.get("flight_number") if isinstance(f, dict) else None) or None
                dt = (f.get("date") if isinstance(f, dict) else None) or None
                if fn and dt and "get_flight_status" in self.tool_names:
                    base = list(chain)
                    base.append(("get_flight_status", {"flight_number": fn, "date": dt}))
                    emit(base, f"Is flight {fn} on {dt} on time?")
        # direct-flight searches between real airports on real dates
        if "search_direct_flight" in self.tool_names and self.index.flights:
            f1 = rng.choice(self.index.flights)
            date_pool = sorted((f1.get("dates") or {}).keys())
            if date_pool:
                dt = rng.choice(date_pool)
                chain = []
                if "get_user_details" in self.tool_names:
                    chain.append(("get_user_details", {"user_id": uid}))
                chain.append(("search_direct_flight", {"origin": f1.get("origin"), "destination": f1.get("destination"), "date": dt}))
                emit(chain, f"Search direct flights from {f1.get('origin')} to {f1.get('destination')} on {dt}.")
        return ops

    def _route_reads_for_airline(self, user: dict) -> list[list[tuple[str, dict]]]:
        routes = [[(n, {"user_id": user.get("user_id")})] for n in ("get_user_details",) if n in self.tool_names]
        return routes or [[]]

    def ops_for_reservation(self, user: dict, res: dict, rng: random.Random) -> list[Op]:
        ops: list[Op] = []
        rid = res.get("reservation_id")
        status = str(res.get("status", ""))
        name = user.get("name") or {}
        routes = [
            [("get_user_details", {"user_id": user.get("user_id")}), ("get_reservation_details", {"reservation_id": rid})]
        ]
        if status != "cancelled" and "cancel_reservation" in self.tool_names:
            ops.append(Op("cancel_reservation", {"reservation_id": rid}, routes[0], f"Cancel reservation {rid} completely."))
        if "update_reservation_baggages" in self.tool_names:
            cur = res.get("baggages") or {}
            total = int(cur.get("total", 0))
            ops.append(Op(
                "update_reservation_baggages",
                {"reservation_id": rid, "cabin": None, "total_baggages": total + 1, "nonfree_baggages": max(0, total + 1 - 2)},
                routes[0],
                f"Add one checked bag to reservation {rid}.",
            ))
        if "book_reservation" in self.tool_names and self.index.flights:
            fl = rng.choice(self.index.flights)
            pays = self._payment_options(user)
            for pay in pays[:4]:
                args = {
                    "user_id": user.get("user_id"),
                    "origin": fl.get("origin"),
                    "destination": fl.get("destination"),
                    "flight_type": "one_way",
                    "cabin": "economy",
                    "flights": [{"date": fl.get("date"), "flight_number": fl.get("flight_number")}],
                    "passengers": [{"first_name": name.get("first_name"), "last_name": name.get("last_name"), "dob": (user.get("dob") or "1990-01-01")}],
                    "payment_methods": [{"payment_id": pay, "amount": 100}],
                    "total_baggages": 1,
                    "nonfree_baggages": 0,
                    "insurance": "no",
                }
                ops.append(Op("book_reservation", args, routes[0], f"Book a one-way economy flight {fl.get('flight_number')} for me, pay with {pay}."))
        return ops

    # ---------- enumeration cores ----------

    def _iter_action_lists(self, breadth: bool) -> Iterator[list[tuple[str, dict]]]:
        """Yield candidate action sequences (name, args) as plain tuples.

        In breadth mode also yields:
        - COMPOUND sequences pairing two independent ops (different entities)
        - FULL-CONTEXT sequences: identity route, user details, every order
          detail, then one/two writes - the dominant hand-authored shape.
        - READ-ONLY information requests.
        """
        rng = self.rng
        users = self.index.users
        rng.shuffle(users)
        for ui, user in enumerate(users):
            uid = str(user.get("user_id"))
            pool: list[tuple[Op, str]] = []
            for order in self.index.orders_by_user.get(uid, []):
                for op in self.ops_for_order(user, order, rng, breadth=breadth):
                    acts = [(n, dict(a)) for n, a in op.reads] + [(op.name, dict(op.args))]
                    yield acts
                    pool.append((op, _primary_entity(op)))
            for op in self.ops_for_user_address(user, rng):
                yield [(op.name, dict(op.args))]
                pool.append((op, _primary_entity(op)))
            for res in self.index.reservations_by_user.get(uid, []):
                for op in self.ops_for_reservation(user, res, rng):
                    acts = [(n, dict(a)) for n, a in op.reads] + [(op.name, dict(op.args))]
                    yield acts
                    pool.append((op, _primary_entity(op)))

            if not breadth:
                continue

            # compound pairs on independent entities
            sample = pool[:400]
            made = 0
            for i in range(len(sample)):
                for j in range(len(sample)):
                    if i == j:
                        continue
                    oa, ea = sample[i]
                    ob, eb = sample[j]
                    if ea is None or eb is None:
                        continue
                    if ea == eb and not (
                        oa.name.startswith("update_reservation") and ob.name.startswith("update_reservation")
                    ):
                        continue
                    reads = list({json.dumps(r, sort_keys=True, default=str): r for r in (oa.reads + ob.reads)}.values())
                    yield reads + [(oa.name, dict(oa.args)), (ob.name, dict(ob.args))]
                    made += 1
                    if made >= 800:
                        break
                if made >= 800:
                    break

            # readonly chains standalone and paired with a write
            ro = self.ops_readonly(user, rng)
            for op in ro:
                yield [(n, dict(a)) for n, a in op.reads]
            if ro and pool:
                bw, ent = pool[rng.randrange(min(len(pool), 200))]
                for op in ro[:6]:
                    yield [(n, dict(a)) for n, a in op.reads] + [(bw.name, dict(bw.args))]

            # FULL-CONTEXT sequences over all of this user's orders
            orders_u = self.index.orders_by_user.get(uid, [])
            if not orders_u:
                continue
            name = user.get("name") or {}
            zipc = (user.get("address") or {}).get("zip")
            id_routes = []
            if "find_user_id_by_email" in self.tool_names:
                id_routes.append([("find_user_id_by_email", {"email": user.get("email")})])
            if "find_user_id_by_name_zip" in self.tool_names:
                id_routes.append([("find_user_id_by_name_zip", {"first_name": name.get("first_name"), "last_name": name.get("last_name"), "zip": zipc})])
            ud = [("get_user_details", {"user_id": uid})] if "get_user_details" in self.tool_names else []
            oreads = [("get_order_details", {"order_id": o["order_id"]}) for o in orders_u[:6]]
            prefixes = []
            seenp = set()
            for r in id_routes:
                for p in (r + ud + oreads, r + oreads, r + ud, r + ud + oreads[:1]):
                    key = json.dumps(p, sort_keys=True, default=str)
                    if key not in seenp:
                        seenp.add(key)
                        prefixes.append(p)
            ops_sample = pool[:250]
            for prefix in prefixes:
                for op, _ent in ops_sample:
                    # focused prefix: only the op's own order read
                    ent = _primary_entity(op)
                    if ent and any(o.get("order_id") == ent for o in orders_u):
                        focus = [("get_order_details", {"order_id": ent})]
                        ref_ids = {str(x) for v in op.args.values() if isinstance(v, list) for x in v}
                        rel_items = []
                        for o in orders_u:
                            if o.get("order_id") == ent:
                                rel_items = [it for it in (o.get("items") or []) if str(it.get("item_id")) in ref_ids]
                                break
                        prods = []
                        seenp3 = set()
                        if "get_product_details" in self.tool_names:
                            for it in rel_items:
                                pid = str(it.get("product_id"))
                                if pid not in seenp3:
                                    seenp3.add(pid)
                                    prods.append(("get_product_details", {"product_id": pid}))
                        base = None
                        for r in id_routes:
                            for withud in (True, False):
                                b = r + (ud if withud else []) + focus
                                yield b + prods + [(op.name, dict(op.args))]
                                yield b + [(op.name, dict(op.args))]
                    # full-context variants
                    ref_ids = {str(x) for v in op.args.values() if isinstance(v, list) for x in v}
                    rel_items = []
                    for o in orders_u:
                        if o.get("order_id") == _primary_entity(op):
                            rel_items = [it for it in (o.get("items") or []) if str(it.get("item_id")) in ref_ids]
                            break
                    prods = []
                    seenp2 = set()
                    if "get_product_details" in self.tool_names:
                        for it in rel_items:
                            pid = str(it.get("product_id"))
                            if pid not in seenp2:
                                seenp2.add(pid)
                                prods.append(("get_product_details", {"product_id": pid}))
                    if prods:
                        yield prefix + prods + [(op.name, dict(op.args))]
                        yield prefix + prods + prods + [(op.name, dict(op.args))]
                    else:
                        yield prefix + [(op.name, dict(op.args))]
                # two writes after full context
                pmade = 0
                for i in range(len(sample)):
                    for j in range(len(sample)):
                        if i == j:
                            continue
                        oa, ea = sample[i]
                        ob, eb = sample[j]
                        if ea == eb or ea is None or eb is None:
                            continue
                        yield prefix + [(oa.name, dict(oa.args)), (ob.name, dict(ob.args))]
                        pmade += 1
                        if pmade >= 120:
                            break
                    if pmade >= 120:
                        break

    def enumerate_signatures(self, cap: int = 20_000_000) -> dict[str, set[str]]:
        """Full-breadth signature sets for rediscovery matching.

        strict:   digest over complete action sequences (frozen D9 definition)
        writes:   digest over mutating actions' names + entity-id bindings only
        """
        from oosc.adapters.corruptions import is_write

        strict: set[str] = set()
        writes: set[str] = set()
        for acts in self._iter_action_lists(breadth=True):
            strict.add(actions_digest(acts))
            w = [(n, {k: v for k, v in a.items() if k.endswith(("_id", "_ids"))}) for n, a in acts if is_write(n)]
            if w:
                writes.add(actions_digest(w))
            if len(strict) >= cap:
                break
        return {"strict": strict, "writes": writes}

    def generate(
        self,
        limit: int | None = None,
        include_adversarial: bool = True,
    ) -> list["Any"]:
        """Bounded scenarios for platform/sandbox use.

        The benchmark-specialized stream is retained for historical
        rediscovery evidence.  A schema-driven stream is always included so a
        previously unseen domain produces useful scenarios immediately.
        ``limit`` lets commit CI avoid materializing 50k objects before it
        downsamples them.
        """
        from oosc.schema import Scenario as ScenarioModel
        from oosc.generate.generic import GenericScenarioGenerator

        generic = GenericScenarioGenerator(self.domain, seed=7)
        generic_realistic = generic.generate_realistic(limit_per_tool=4)
        generic_adversarial = (
            generic.generate_adversarial(generic_realistic, limit=16)
            if include_adversarial
            else []
        )
        scenarios: list[ScenarioModel] = generic_realistic + generic_adversarial
        target = min(self.budget, 50000) if limit is None else max(1, limit)
        if len(scenarios) >= target:
            return scenarios[:target]
        counter = 0
        for acts in self._iter_action_lists(breadth=False):
            counter += 1
            *reads, write = acts
            scenarios.append(
                ScenarioModel(
                    id=f"{self.domain.name}-gen-{counter:06d}",
                    domain=self.domain.name,
                    category="realistic",
                    instructions=f"Scenario {counter}: perform {write[0]}.",
                    criteria=TaskCriteria(
                        actions=[ActionDef(name=n, arguments=a) for n, a in acts],
                        reward_basis=["DB", "ACTION"],
                    ),
                    meta={"op": write[0]},
                )
            )
            if len(scenarios) >= target:
                break
        return scenarios
