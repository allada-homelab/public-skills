import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evidence_ledger import EvidenceLedger  # noqa: E402


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()
        self.bundle = self.project / "llm-wiki"
        self.bundle.mkdir()
        (self.bundle / "index.md").write_text("# Wiki\n", encoding="utf-8")
        (self.project / "a.py").write_text("A = 1\n", encoding="utf-8")
        (self.project / "b.py").write_text("B = 1\n", encoding="utf-8")
        for args in (
            ("init", "-q"),
            ("config", "user.email", "test@example.com"),
            ("config", "user.name", "Test"),
            ("add", "a.py", "b.py", "llm-wiki/index.md"),
            ("commit", "-qm", "baseline"),
        ):
            subprocess.run(["git", "-C", str(self.project), *args], check=True)

    def event(self, path, tool="Write", agent_type=None):
        value = {
            "hook_event_name": "PostToolUse",
            "session_id": "session-a",
            "cwd": str(self.project),
            "tool_name": tool,
            "tool_input": {"file_path": str(path)},
        }
        if agent_type is not None:
            value["agent_type"] = agent_type
        return value

    def test_dedupes_paths_and_distinguishes_preexisting_dirty_changes(self):
        (self.project / "a.py").write_text("A = 2\n", encoding="utf-8")
        ledger = EvidenceLedger(self.project, "session-a")
        baseline = ledger.initialize()
        self.assertIn("a.py", baseline["dirty_hashes"])

        (self.project / "b.py").write_text("B = 2\n", encoding="utf-8")
        self.assertTrue(ledger.record_tool_event(self.event(self.project / "b.py", "Write")))
        self.assertTrue(ledger.record_tool_event(self.event(self.project / "b.py", "Edit")))
        self.assertFalse(ledger.record_tool_event(self.event(
            self.bundle / "generated.md", "Write", "llm-wiki:wiki-capturer"
        )))

        first, path = ledger.finalize()
        self.assertEqual(
            [item["path"] for item in first["payload"]["changed_paths"]], ["b.py"]
        )
        self.assertEqual(first["payload"]["changed_paths"][0]["source"], "edit")
        self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8")), first)

        (self.project / "a.py").write_text("A = 3\n", encoding="utf-8")
        second, _ = ledger.finalize()
        self.assertEqual(
            [item["path"] for item in second["payload"]["changed_paths"]],
            ["a.py", "b.py"],
        )

    def test_session_state_is_isolated(self):
        first = EvidenceLedger(self.project, "a/b")
        second = EvidenceLedger(self.project, "a_b")
        self.assertNotEqual(first.root, second.root)
        first.initialize()
        second.initialize()
        self.assertTrue(Path(first.baseline_path).is_file())
        self.assertTrue(Path(second.baseline_path).is_file())


if __name__ == "__main__":
    unittest.main()
