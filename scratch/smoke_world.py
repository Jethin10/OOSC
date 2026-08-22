import json
from oosc.schema import DomainDef
from oosc.world.derive import WorldSpec

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
spec = WorldSpec(dom)
s = spec.summary()
for name in ["cancel_pending_order","exchange_delivered_order_items","modify_pending_order_address",
             "return_delivered_order_items","get_order_details","find_user_id_by_name_zip",
             "modify_pending_order_items","transfer_to_human_agents","calculate"]:
    print(name, "->", json.dumps(s["effects"][name]))
print()
domA = DomainDef.model_validate(json.load(open("results/repro/schema/airline.domain.json")))
specA = WorldSpec(domA)
sA = specA.summary()
for name in ["book_reservation","cancel_reservation","update_reservation_flights","send_certificate","search_direct_flight","get_flight_status"]:
    print(name, "->", json.dumps(sA["effects"][name]))
