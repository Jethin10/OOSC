import json, sys
sys.path.insert(0, "engine")
from collections import Counter
from oosc.adapters.corruptions import is_write

rep = json.load(open("results/n2/report.json"))
theirs = {d: json.load(open(f"results/repro/schema/{d}.tasks.json")) for d in ("retail","airline")}
doms = {d: json.load(open(f"results/repro/schema/{d}.domain.json")) for d in ("retail","airline")}
orders = {}
for d in doms:
    orders[d] = {o["order_id"] if "order_id" in o else o.get("reservation_id"): o for t in doms[d]["tables"] if t["name"] in ("orders","reservations") for o in t["records"]}
misses = set()
for d in ("retail","airline"):
    for m in rep[d].get("misses_sample", []):
        misses.add((d, m["task"]))
# misses_sample truncated at 25 - recompute full miss list from report? Not stored. Recompute quickly using stored digests? Skip: analyze ALL tasks' shapes instead.
cats = Counter()
for d in ("retail","airline"):
    for t in theirs[d]:
        acts = [a for a in t["criteria"]["actions"]]
        ws = [a for a in acts if is_write(a["name"])]
        ents = set()
        free_text = False
        multi_order = False
        seen_oid = set()
        for a in ws:
            for k, v in a["arguments"].items():
                if k.endswith(("_id","_ids")):
                    vs = v if isinstance(v, list) else [v]
                    for x in vs:
                        ents.add(str(x)[:4])
                        if k == "order_id" or k=="reservation_id":
                            seen_oid.add(str(x))
            for k, v in a["arguments"].items():
                if isinstance(v, str) and (" " in v) and not v.startswith("#") and k not in ("reason","expression","summary"):
                    # heuristic: address-like / name-like payloads
                    if any(c.isdigit() for c in v) or k.startswith(("address","city","state","zip","first","last","email")):
                        free_text = True
        cats[(d, len(ws), "multi_ent" if len(seen_oid)>1 else "single_ent", "freetext" if free_text else "")] += 1
for k, v in sorted(cats.items()):
    print(k, v)
