import json, sys, random
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator
from oosc.schema import DomainDef
dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
idx = gen.index
u = next(u for u in idx.users if u["user_id"]=="mei_kovacs_8020")
orders_u = idx.orders_by_user["mei_kovacs_8020"]
print("mei orders:", [o["order_id"] for o in orders_u])
o = next(o for o in orders_u if o["order_id"]=="#W6390527")
ops = gen.ops_for_order(u, o, random.Random(1), breadth=True)
want = ("return_delivered_order_items", {"order_id": "#W6390527", "item_ids": ["8538875209"], "payment_method_id": "paypal_7644869"})
hits = [op for op in ops if op.name==want[0] and op.args==want[1]]
print("exact return op generated:", len(hits))
if hits:
    print("chains:", [(n, a) for n,a in hits[0].reads])
