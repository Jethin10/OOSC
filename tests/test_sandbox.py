import unittest

from oosc.oracle import TrajectoryStep
from oosc.runner.sandbox import Sandbox, verify_replay
from oosc.schema import ActionDef, TaskCriteria
from tests.test_derive import devops_domain


class SandboxTests(unittest.TestCase):
    def test_text_step_is_recorded_once_and_replays(self):
        domain = devops_domain()
        criteria = TaskCriteria(
            actions=[ActionDef(name="restart_instance", arguments={"instance_id": "inst_1"})]
        )
        steps = [
            TrajectoryStep(calls=[{"name": "restart_instance", "arguments": {"instance_id": "inst_1"}}]),
            TrajectoryStep(text="Done successfully."),
        ]
        trace, verdict = Sandbox(domain).run("devops-1", steps, criteria)
        self.assertEqual(len(trace.steps), 2)
        self.assertEqual(verdict.reward, 1.0)
        self.assertEqual(verify_replay(domain, trace), (True, []))


if __name__ == "__main__":
    unittest.main()
