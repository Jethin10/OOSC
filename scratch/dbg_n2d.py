import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
scen = ScenarioGenerator(dom).generate()
their = json.load(open("results/repro/schema/retail.tasks.json"))
t0 = their[0]
cands = [s for s in scen if any(a.name=="exchange_delivered_order_items" and a.arguments.get("item_ids")==["1151293680","4983901480"] for a in s.criteria.actions)]
print("candidate scenarios:", len(cands))
want_actions = [(a["name"], json.dumps(a["arguments"], sort_keys=True)) for a in t0["criteria"]["actions"]]
for s in cands[:4]:
    got = [(a.name, json.dumps(a.arguments, sort_keys=True)) for a in s.criteria.actions]
    print("MATCH!" if got == want_actions else "diff:")
    if got != want_actions:
        for w, g in zip(want_actions, got):
            if w != g:
                print("  their:", w)
                print("  ours :", g)
        if len(want_actions) != len(got): print("  len", len(want_actions), "vs", len(got))
