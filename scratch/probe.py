import json
from tau2.registry import registry
env = registry.get_env_constructor('retail')()
tools = env.get_tools()
t = [x for x in tools if x.name == 'cancel_pending_order'][0]
print("SHORT:", t.short_desc)
print("LONG:", (t.long_desc or "")[:400])
print("PARAM SCHEMA:", json.dumps(t.params.model_json_schema(), indent=1)[:900])
print("RETURNS:", t.returns.model_json_schema().get('title'))
print("RAISES:", json.dumps(t.raises)[:300])
print()
sigs = [x.name for x in tools]
print(sorted(sigs))
# airline
env2 = registry.get_env_constructor('airline')()
print("AIRLINE TOOLS:", sorted(x.name for x in env2.get_tools()))
