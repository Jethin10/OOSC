import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator
from oosc.schema import DomainDef
import importlib.util as _iu
_sp = _iu.spec_from_file_location("run_n2", "scripts/run_n2.py")
_m = _iu.module_from_spec(_sp)
_sp.loader.exec_module(_m)
strict_sig, structural_sig = _m.strict_sig, _m.structural_sig

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
scen = gen.generate()
print("total scenarios:", len(scen))
their = json.load(open("results/repro/schema/retail.tasks.json"))
t0 = their[0]
ss = strict_sig(t0["criteria"]["actions"])
st = structural_sig(t0["criteria"]["actions"])
print("their sig:", ss)
# find scenarios touching same order
hits = [s for s in scen if any("#W2378156" in json.dumps(a.arguments) for a in s.criteria.actions)]
print("scenarios touching #W2378156:", len(hits))
for s in hits[:3]:
    print(" GEN:", [(a.name, a.arguments.get("order_id"), a.arguments.get("item_ids"), a.arguments.get("new_item_ids")) for a in s.criteria.actions])
    print("  strict equal:", strict_sig([a.model_dump() for a in s.criteria.actions]) == ss)
