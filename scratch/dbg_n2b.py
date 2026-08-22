import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
idx = gen.index
# does the user exist?
u = idx.user("yusuf_rossi_4930")
print("user by guess:", bool(u))
# find user by name
cands = [u for u in idx.users if (u.get("name") or {}).get("first_name") == "Yusuf"]
print("users named Yusuf:", [(u["user_id"], u.get("reservations")) for u in cands][:5])
yusuf = cands[0] if cands else None
if yusuf:
    uid = yusuf["user_id"]
    print("orders of yusuf:", [o["order_id"] + ":" + o["status"] for o in idx.orders_by_user.get(uid, [])])
    # is W2378156 his?
    o = next((o for o in idx.orders_by_user.get(uid, []) if o["order_id"] == "#W2378156"), None)
    print("W2378156 found:", bool(o))
    if o:
        ops = gen.ops_for_order(yusuf, o, __import__("random").Random(1))
        print("ops for that order:", len(ops))
        from collections import Counter
        print(Counter(op.name for op in ops))
