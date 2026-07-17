from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from job_state import JobController  # noqa: E402


class JobControllerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        bundle = self.project / "llm-wiki"
        bundle.mkdir(parents=True)
        (bundle / "index.md").write_text("# Wiki\n", encoding="utf-8")
        self.clock = [1000]
        self.controller = JobController(
            self.project, "session-a", now=lambda: self.clock[0]
        )

    def test_idempotency_budget_release_and_kill_switch(self):
        budget = {"calls": 1, "turns": 4, "seconds": 30, "descendants": 0}
        first, duplicate = self.controller.propose(
            "recall", "user_prompt", "recall:a", budget, "synthesizer"
        )
        self.assertFalse(duplicate)
        again, duplicate = self.controller.propose(
            "recall", "user_prompt", "recall:a", budget, "synthesizer"
        )
        self.assertTrue(duplicate)
        self.assertEqual(again["packet_id"], first["packet_id"])
        self.assertTrue(self.controller.start(first["packet_id"]))
        self.assertTrue(self.controller.accept_result(first["packet_id"], "context_capsule"))

        second, _ = self.controller.propose(
            "recall", "user_prompt", "recall:b", budget, "synthesizer"
        )
        self.assertEqual(second["payload"]["state"], "pending")

        settings = self.project / ".claude" / "llm-wiki.local.md"
        settings.parent.mkdir()
        settings.write_text("---\nautonomy: off\n---\n", encoding="utf-8")
        blocked, _ = self.controller.propose(
            "impact", "user_prompt", "impact:a", budget, "worker"
        )
        self.assertEqual(blocked["payload"]["state"], "blocked")
        explicit, _ = self.controller.propose(
            "capture", "user_command", "capture:a", budget, "publisher"
        )
        self.assertEqual(explicit["payload"]["state"], "pending")

    def test_children_are_bounded_and_cancelled_parent_rejects_late_work(self):
        parent, _ = self.controller.propose(
            "recall",
            "user_prompt",
            "recall:parent",
            {"calls": 3, "turns": 20, "seconds": 120, "descendants": 2},
            "synthesizer",
            allow_descendants=True,
            allowed_features=("parallel",),
        )
        self.assertTrue(self.controller.start(parent["packet_id"]))
        children = []
        for index in range(3):
            child, _ = self.controller.propose(
                "parallel",
                "plugin:recall",
                "worker:%d" % index,
                {"calls": 1, "turns": 6, "seconds": 30, "descendants": 0},
                "worker",
                parent_id=parent["packet_id"],
            )
            children.append(child)
        self.assertEqual([child["payload"]["state"] for child in children], [
            "pending", "pending", "blocked"
        ])
        self.assertTrue(self.controller.start(children[0]["packet_id"]))
        self.assertFalse(self.controller.accept_result(children[0]["packet_id"], "context_capsule"))
        self.assertTrue(self.controller.cancel(parent["packet_id"]))
        self.assertFalse(self.controller.accept_result(children[0]["packet_id"], "evidence_packet"))
        self.assertFalse(self.controller.start(children[1]["packet_id"]))
        self.assertEqual(
            self.controller.get(children[1]["packet_id"])["payload"]["state"], "cancelled"
        )

    def test_plugin_origin_requires_parent_and_retry_is_once(self):
        budget = {"calls": 1, "turns": 4, "seconds": 30, "descendants": 0}
        blocked, _ = self.controller.propose(
            "gap", "plugin:recall", "gap:orphan", budget, "worker"
        )
        self.assertEqual(blocked["payload"]["state"], "blocked")

        job, _ = self.controller.propose(
            "recall", "user_prompt", "recall:retry", budget, "synthesizer"
        )
        self.assertTrue(self.controller.start(job["packet_id"]))
        self.assertTrue(self.controller.attempt_failed(job["packet_id"], "first"))
        self.assertFalse(self.controller.attempt_failed(job["packet_id"], "second"))
        self.assertEqual(self.controller.get(job["packet_id"])["payload"]["state"], "failed")

    def test_preissued_publisher_can_start_after_parent_completed(self):
        parent, _ = self.controller.propose(
            "gap", "user_prompt", "gap:parent",
            {"calls": 1, "turns": 12, "seconds": 60, "descendants": 1},
            "worker", allow_descendants=True, allowed_features=("scribe",),
        )
        self.assertTrue(self.controller.start(parent["packet_id"]))
        child, _ = self.controller.propose(
            "scribe", "plugin:gap", "scribe:child",
            {"calls": 1, "turns": 12, "seconds": 60, "descendants": 0},
            "publisher", parent_id=parent["packet_id"],
        )
        self.assertTrue(self.controller.accept_result(parent["packet_id"], "evidence_packet"))
        self.assertTrue(self.controller.start(child["packet_id"]))

    def test_cancel_tree_reaches_pending_child_after_parent_completed(self):
        parent, _ = self.controller.propose(
            "gap", "user_prompt", "gap:tree",
            {"calls": 1, "turns": 12, "seconds": 60, "descendants": 1},
            "worker", allow_descendants=True, allowed_features=("scribe",),
        )
        self.assertTrue(self.controller.start(parent["packet_id"]))
        child, _ = self.controller.propose(
            "scribe", "plugin:gap", "scribe:tree",
            {"calls": 1, "turns": 12, "seconds": 60, "descendants": 0},
            "publisher", parent_id=parent["packet_id"],
        )
        self.assertTrue(self.controller.accept_result(parent["packet_id"], "evidence_packet"))
        self.assertTrue(self.controller.cancel_tree(parent["packet_id"]))
        self.assertEqual(
            self.controller.get(child["packet_id"])["payload"]["state"], "cancelled"
        )


if __name__ == "__main__":
    unittest.main()
