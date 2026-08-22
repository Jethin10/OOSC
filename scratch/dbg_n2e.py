import json, sys
sys.path.insert(0, "engine")
from oosc.generate.engine import ScenarioGenerator, WorldIndex
from oosc.schema import DomainDef

dom = DomainDef.model_validate(json.load(open("results/repro/schema/retail.domain.json")))
gen = ScenarioGenerator(dom)
idx = gen.index
u = idx.user("yusuf_rossi_9620")
o = next(o for o in idx.orders_by_user["yusuf_rossi_9620"] if o["order_id"] == "#W2378156")
print("items:", [(i["item_id"], i["product_id"], i.get("options")) for i in o["items"]])
ops = gen.ops_for_order(u, o, __import__("random").Random(3))
ex = [op for op in ops if op.name == "exchange_delivered_order_items"]
print("exchange ops:", len(ex))
pairs = {(tuple(op.args["item_ids"]), tuple(op.args["new_item_ids"])) for op in ex}
print("has target pair:", (("1151293680","4983901480"), ("7706410293","7747408585")) in pairs)
# what alts exist per item?
for it in o["items"]:
    print(it["item_id"], "alts:", gen._variant_alternatives(it["product_id"], it["item_id"]))
