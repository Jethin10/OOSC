import tempfile
import unittest
from pathlib import Path

from oosc.score.history import compare_snapshots, persist_snapshot, previous_snapshot


def card(rate: float) -> dict:
    successes = int(rate * 10)
    return {
        "overall": {"runs": 10, "successes": successes, "reliability": rate, "ci95": [rate, rate]},
        "categories": [
            {"category": "write", "runs": 10, "successes": successes, "reliability": rate, "ci95": [rate, rate]}
        ],
    }


class HistoryTests(unittest.TestCase):
    def test_persists_and_detects_cross_run_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = {"domain": "devops", "scorecards": {"agent-v1": card(1.0)}}
            persist_snapshot(root, first)
            _, loaded = previous_snapshot(root, "devops")
            result = compare_snapshots(loaded, {"domain": "devops", "scorecards": {"agent-v1": card(0.0)}})
            self.assertFalse(result["gate_pass"])
            self.assertEqual(result["comparisons"]["agent-v1"]["overall_delta"], -1.0)


if __name__ == "__main__":
    unittest.main()
