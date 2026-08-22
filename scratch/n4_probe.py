import sys
sys.path.insert(0, "vendor/agentdojo/src")
from agentdojo.attacks.attack_registry import ATTACKS
print("registered attacks:", sorted(ATTACKS.keys()))
from agentdojo.task_suite.load_suites import get_suite
suite = get_suite("v1", "workspace")
print("workspace user_tasks:", len(suite.user_tasks), "injection_tasks:", len(suite.injection_tasks))
env = suite.load_and_inject_default_environment({})
print("env type:", type(env).__name__)
# pick a user task + injection task
ut = next(iter(suite.user_tasks.values()))
it = next(iter(suite.injection_tasks.values()))
print("user task:", ut.ID, "| injection GOAL:", getattr(it, "GOAL", None))
from agentdojo.functions_runtime import FunctionsRuntime
runtime = FunctionsRuntime(suite.tools)
pre_env = env.model_copy(deep=True)
for call in ut.ground_truth(pre_env):
    res, err = runtime.run_function(env, call.function, call.args)
    if err: print("GT err:", err)
util_ok = ut.utility(ut.GROUND_TRUTH_OUTPUT, pre_env, env)
print("utility of ground truth:", util_ok)
# now vulnerable victim: user GT then injection GT
for call in it.ground_truth(pre_env):
    res, err = runtime.run_function(env, call.function, call.args)
    if err: print("inj GT err:", err)
sec = it.security(it.GROUND_TRUTH_OUTPUT, pre_env, env)
print("security after vuln victim (True=attack succeeded):", sec)
