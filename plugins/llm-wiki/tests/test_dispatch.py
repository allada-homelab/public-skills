from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dispatch import select_job  # noqa: E402
from job_state import JobController, public_job_record  # noqa: E402


class DispatchSelectionTests(unittest.TestCase):
    def test_recall_target_ignores_nested_worker_job_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            bundle = project / "llm-wiki"
            bundle.mkdir()
            (bundle / "index.md").write_text("# Wiki\n", encoding="utf-8")
            controller = JobController(project, "session")
            parent, _ = controller.propose(
                "recall", "user_prompt", "recall:one",
                {"calls": 3, "turns": 20, "seconds": 120, "descendants": 2},
                "synthesizer", allow_descendants=True, allowed_features=("parallel",),
            )
            child, _ = controller.propose(
                "parallel", "system:planner", "worker:one",
                {"calls": 1, "turns": 6, "seconds": 30, "descendants": 0},
                "worker", parent_id=parent["packet_id"],
            )
            event = {
                "tool_name": "Skill",
                "tool_input": {
                    "skill": "llm-wiki:recall",
                    "args": str({"parent": public_job_record(parent), "child": public_job_record(child)}),
                },
            }
            selected = select_job(controller, event)
            self.assertEqual(selected["packet_id"], parent["packet_id"])


if __name__ == "__main__":
    unittest.main()
