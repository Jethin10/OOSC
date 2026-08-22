import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, actions_digest
from oosc.schema import DomainDef
dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
their = json.load(open("results/repro/schema/retail.tasks.json"))
t5 = their[5]
acts = [(a["name"], a["arguments"]) for a in t5["criteria"]["actions"]]
d_want = actions_digest(acts)
print("want:", json.dumps(acts))
found = False
for seq in gen._iter_action_lists(breadth=True):
    if any(n=="return_delivered_order_items" for n,_ in seq) and any(a.get("order_id")=="#W6390527" for _,a in seq):
        if seq == acts:
            found = True
            pass
print("exact sequence yielded:", found)
if not found:
    # print our closest
    gen2 = ScenarioGenerator(dom)
    u = next(u for u in gen.index.users if u["user_id"]=="mei_kovacs_8020")
    o = next(o for o in gen.index.orders_by_user["mei_kovacs_8020"] if o["order_id"]=="#W6390527")
    import random
    for op in gen.ops_for_order(u,o,random.Random(1),breadth=True):
        if op.name=="return_delivered_order_items" and op.args==acts[-1][1]:
            print("our seq:", [(n,a) for n,a in [(n, dict(a)) for n,a in op.reads]] + [("return_delivered_order_items", dict(op.args))])
            pass
