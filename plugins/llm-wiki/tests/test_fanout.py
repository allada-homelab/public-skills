from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fanout import plan_fanout  # noqa: E402


CANDIDATES = [
    {"path": "auth/tokens.md", "section_path": "auth"},
    {"path": "billing/retries.md", "section_path": "billing"},
    {"path": "ops/rollback.md", "section_path": "ops"},
]


class FanoutPlannerTests(unittest.TestCase):
    def test_glimmer_and_single_section_stay_sequential(self):
        self.assertEqual(plan_fanout(CANDIDATES, {"route": "glimmer"})["mode"], "sequential")
        self.assertEqual(
            plan_fanout(CANDIDATES[:1], {"route": "oracle"})["mode"], "sequential"
        )

    def test_oracle_and_archaeologist_have_stable_disjoint_caps(self):
        oracle = plan_fanout(CANDIDATES, {"route": "oracle"})
        archaeologist = plan_fanout(CANDIDATES, {"route": "archaeologist"})
        self.assertEqual(len(oracle["workers"]), 2)
        self.assertEqual(len(archaeologist["workers"]), 3)
        for plan in (oracle, archaeologist):
            paths = [path for worker in plan["workers"] for path in worker["candidate_paths"]]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertTrue(all(worker["turn_budget"] == 6 for worker in plan["workers"]))


if __name__ == "__main__":
    unittest.main()
