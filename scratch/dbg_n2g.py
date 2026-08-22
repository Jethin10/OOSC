import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, actions_digest
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
their = json.load(open("results/repro/schema/retail.tasks.json"))
t0 = their[0]
acts = [(a["name"], a["arguments"]) for a in t0["criteria"]["actions"]]
d = actions_digest(acts)
sigs = gen.enumerate_signatures()
print("task0 digest in strict set:", d in sigs["strict"])
print("strict size:", len(sigs["strict"]))
# check writes-only digest too
w = [(n, {k:v for k,v in a.items() if k.endswith(("_id","_ids"))}) for n,a in acts if not n.startswith(("find","get","list","search","calculate"))]
print("writes digest:", actions_digest(w) in sigs["writes"])
