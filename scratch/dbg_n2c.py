import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
scen = gen.generate()
their = json.load(open("results/repro/schema/retail.tasks.json"))
t0 = their[0]
want = t0["criteria"]["actions"][-1]["arguments"]
print("want write args:", json.dumps(want, sort_keys=True))
hits = [s for s in scen if any(a.arguments.get("order_id") == "#W2378156" and a.name == "exchange_delivered_order_items" for a in s.criteria.actions)]
print("exchange ops on that order:", len(hits))
for s in hits[:6]:
    w = [a for a in s.criteria.actions if a.name.startswith("exchange")][0]
    print("  got:", json.dumps(w.arguments, sort_keys=True))
    print("  chain:", [a.name for a in s.criteria.actions])
