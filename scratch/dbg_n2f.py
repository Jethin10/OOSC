import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, actions_digest
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
their = json.load(open("results/repro/schema/retail.tasks.json"))

# find a miss where the write matches some generated write
rep = json.load(open("results/n1/report.json"))  # just to have something
# collect generated seqs containing a given write
target = None
for t in their:
    acts = t["criteria"]["actions"]
    ws = [a for a in acts if "exchange" in a["name"] or "return" in a["name"]]
    if len(acts) >= 4 and ws:
        target = t
        break
print("TASK", target["id"])
for a in target["criteria"]["actions"]:
    print("  gold:", a["name"], json.dumps(a["arguments"])[:130])

want_write = [a for a in target["criteria"]["actions"] if a["name"] not in ("find_user_id_by_email","find_user_id_by_name_zip","get_user_details","get_order_details","get_product_details")][0]
oid = want_write["arguments"].get("order_id")
uid = None
orders = {x["order_id"]: x for x in dom.tables[2].records}
if oid in orders: uid = orders[oid]["user_id"]
print("order user:", uid)
u = gen.index.user(uid) if uid else None
o = next((o for o in gen.index.orders_by_user.get(uid, []) if o["order_id"] == oid), None)
ops = gen.ops_for_order(u, o, __import__("random").Random(9), breadth=True)
same = [op for op in ops if op.name == want_write["name"] and json.dumps(op.args, sort_keys=True) == json.dumps(want_write["arguments"], sort_keys=True)]
print("generated ops w/ exact same args:", len(same))
for op in same[:3]:
    print("  our chain:", [(n, json.dumps(a)) for n, a in op.reads])
