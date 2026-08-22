import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, actions_digest
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
sigs = gen.enumerate_signatures()
their = json.load(open("results/repro/schema/retail.tasks.json"))
n = 0
for t in their:
    acts = [(a["name"], a["arguments"]) for a in t["criteria"]["actions"]]
    if not acts: continue
    if actions_digest(acts) not in sigs["strict"]:
        n += 1
        if n > 18: break
        print(f"--- task {t['id']}")
        for nm, ar in acts:
            print("   ", nm, json.dumps(ar)[:110])
