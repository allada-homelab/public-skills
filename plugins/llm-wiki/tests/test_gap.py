import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gap import (  # noqa: E402
    extract_packet,
    proposal_key,
    publication_policy,
    source_manifest,
    store_result,
)
from packet_contracts import SCHEMA, VERSION  # noqa: E402


class GapPolicyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        (self.project / "src").mkdir(parents=True)
        (self.project / "tests").mkdir()
        (self.project / "llm-wiki").mkdir()
        (self.project / "src" / "feature.py").write_text("ENABLED = True\n", encoding="utf-8")
        (self.project / "tests" / "test_feature.py").write_text(
            "def test_enabled(): assert True\n", encoding="utf-8"
        )
        (self.project / ".env").write_text("SECRET=fixture\n", encoding="utf-8")
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
        (self.project / "llm-wiki" / "index.md").write_text("# Wiki\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "src", "tests"], cwd=self.project, check=True)
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
               "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.project, env=env, check=True)
        self.head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.project, text=True
        ).strip()

    def packet(self, question="How is the feature enabled?"):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "kind": "evidence_packet",
            "packet_id": "gap-evidence",
            "run_id": "run-gap",
            "payload": {
                "repository": "project",
                "worktree": str(self.project),
                "branch": "main",
                "base_head": self.head,
                "session_id": "session-gap",
                "revision": self.head,
                "changed_paths": [],
                "purpose": "gap_research",
                "job_id": "job-00000000000000000000",
                "source_manifest_sha256": "sha256:" + ("a" * 64),
                "status": "candidate",
                "question": question,
                "task_scope": "repository",
                "risk": "objective",
                "confidence": 0.94,
                "claims": [{
                    "statement": "The feature is enabled.",
                    "classification": "observed",
                    "scope": "repository",
                    "sources": [
                        {"source": "src/feature.py", "source_kind": "code"},
                        {"source": "tests/test_feature.py", "source_kind": "test"},
                    ],
                }],
                "candidate": {
                    "type": "reference",
                    "title": "Feature enablement",
                    "slug": "feature-enablement",
                    "description": "How feature enablement is represented.",
                    "body_markdown": "# Feature enablement\n\nThe feature is enabled in code and tests.",
                },
            },
        }

    def test_objective_code_and_test_candidate_is_eligible(self):
        decision = publication_policy(
            self.project, self.packet(), ["src/feature.py", "tests/test_feature.py"]
        )
        self.assertTrue(decision["allowed"], decision)
        self.assertEqual(set(decision["source_hashes"]), {
            "src/feature.py", "tests/test_feature.py"
        })

    def test_risky_or_weak_candidate_is_quarantined(self):
        risky = self.packet("What is our security policy?")
        decision = publication_policy(
            self.project, risky, ["src/feature.py", "tests/test_feature.py"]
        )
        self.assertFalse(decision["allowed"])
        path = store_result(
            self.project, "session-gap", "job-00000000000000000000", risky, decision
        )
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertFalse(record["publication_allowed"])
        self.assertNotIn("candidate", record)

        hidden_risk = self.packet()
        hidden_risk["payload"]["candidate"]["body_markdown"] = "This defines our security policy."
        self.assertFalse(publication_policy(
            self.project, hidden_risk, ["src/feature.py", "tests/test_feature.py"]
        )["allowed"])

        weak = self.packet()
        weak["payload"]["claims"][0]["sources"] = [
            {"source": "src/feature.py", "source_kind": "code"}
        ]
        self.assertFalse(publication_policy(
            self.project, weak, ["src/feature.py", "tests/test_feature.py"]
        )["allowed"])

    def test_manifest_and_idempotency_are_bounded(self):
        manifest = source_manifest(self.project, ["src/feature.py"])
        self.assertIn("src/feature.py", manifest)
        self.assertNotIn(".env", manifest)
        self.assertNotIn(".claude/settings.local.json", manifest)
        self.assertFalse(any(path.startswith("llm-wiki/") for path in manifest))
        self.assertEqual(
            proposal_key("  HOW is X? ", "Repo", self.head),
            proposal_key("how is x?", " repo ", self.head),
        )
        packet = self.packet()
        self.assertEqual(extract_packet({"content": json.dumps(packet)}, "evidence_packet"), packet)


if __name__ == "__main__":
    unittest.main()
