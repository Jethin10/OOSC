import unittest

from oosc.generate.engine import ScenarioGenerator
from oosc.runner.policies import CleanAgent
from oosc.runner.sandbox import Sandbox
from tests.test_derive import devops_domain


class GenerationTests(unittest.TestCase):
    def test_unseen_domain_generates_grounded_realistic_scenarios(self):
        domain = devops_domain()
        scenarios = ScenarioGenerator(domain).generate(limit=30)
        realistic = [s for s in scenarios if s.category == "realistic"]
        self.assertGreaterEqual(len(realistic), 2)
        self.assertEqual({s.meta["generator"] for s in realistic}, {"schema-driven"})
        for scenario in realistic:
            _, verdict = Sandbox(domain).run(scenario.id, CleanAgent().act(scenario), scenario.criteria)
            self.assertEqual(verdict.reward, 1.0)

    def test_adversarial_pressure_ambiguity_conflict_and_injection_are_emitted(self):
        scenarios = ScenarioGenerator(devops_domain()).generate(limit=30)
        categories = {s.category for s in scenarios}
        self.assertTrue(
            {
                "adversarial:pressure",
                "adversarial:ambiguity",
                "adversarial:conflict",
                "adversarial:injected_output",
            }.issubset(categories)
        )


if __name__ == "__main__":
    unittest.main()
