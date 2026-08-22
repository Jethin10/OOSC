import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, actions_digest
from oosc.schema import DomainDef
dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
their = json.load(open("results/repro/schema/retail.tasks.json"))
t5 = their[5]
acts = [(a["name"], a["arguments"]) for a in t5["criteria"]["actions"]]
print("task5:", [a[0] for a in acts])
d = actions_digest(acts)
sigs = gen.enumerate_signatures()
print("task5 strict hit:", d in sigs["strict"])
