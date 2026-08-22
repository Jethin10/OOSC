import json
from oosc.schema import DomainDef
from oosc.world.derive import WorldSpec
from oosc.world.world import MockWorld

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
spec = WorldSpec(dom)
w = MockWorld(spec)
args = {"order_id": "#W4923227", "payment_method_id": "credit_card_8897086"}
r = w.call("modify_pending_order_payment", args)
print("result:", r.ok, r.error, r.mutated, r.bindings)
# what's the order's status?
for i, o in enumerate(w.tables["orders"]):
    if o.get("order_id") == "#W4923227":
        print("order idx", i, "status:", o["status"], "| user:", o.get("user_id"))
        break
eff = spec.effects["modify_pending_order_payment"]
print("effect:", eff.kind, "req:", eff.required_statuses, "blocking:", eff.blocking_statuses, "target:", eff.target_status, "one_shot:", eff.one_shot)
