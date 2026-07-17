from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from doctor import check_concept  # noqa: E402
from packet_contracts import SCHEMA, VERSION, validate_packet  # noqa: E402
from provenance import extract, file_fingerprint, freshness  # noqa: E402
from publication import prepare  # noqa: E402


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        source = self.project / "src" / "cache.py"
        source.parent.mkdir(parents=True)
        source.write_text("TTL = 60\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.project), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.project), "add", "src/cache.py"], check=True)
        subprocess.run(["git", "-C", str(self.project), "commit", "-qm", "baseline"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.project), "rev-parse", "HEAD"], text=True
        ).strip()
        self.digest = file_fingerprint(self.project, "src/cache.py")

    def packet(self):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "kind": "publication_request",
            "packet_id": "publication-cache",
            "run_id": "run-test",
            "payload": {
                "evidence_packet_id": "evidence-test",
                "project": str(self.project),
                "bundle_root": str(self.project / "llm-wiki"),
                "concept_path": "cache-ttl.md",
                "content": "---\ntype: reference\ntitle: Cache TTL\n---\n# Cache TTL\n\nThe cache TTL is 60 seconds.\n",
                "claims": [{
                    "statement": "The cache TTL is 60 seconds.",
                    "classification": "observed",
                    "scope": "repository",
                    "sources": [{"source": "src/cache.py", "source_kind": "code"}],
                }],
                "expected_head": self.head,
                "source_hashes": {"src/cache.py": self.digest},
                "log_kind": "Creation",
                "log_message": "Added cache TTL.",
                "plugin_version": "0.1.0",
            },
        }

    def test_prepare_stamps_valid_provenance_and_detects_dirty_drift(self):
        packet = self.packet()
        validate_packet(packet, "publication_request")
        output = self.project / "prepared.md"
        self.assertEqual(prepare(packet, output)["status"], "prepared")
        content = output.read_text(encoding="utf-8")
        self.assertIn("wiki_managed: true", content)
        document = extract(content)
        self.assertIsNotNone(document)
        self.assertEqual(set(freshness(document, self.project).values()), {"fresh"})
        findings = []
        check_concept(content, "cache-ttl.md", findings)
        self.assertEqual([item for item in findings if item["severity"] == "ERROR"], [])

        (self.project / "src" / "cache.py").write_text("TTL = 30\n", encoding="utf-8")
        stale = prepare(packet, self.project / "stale.md")
        self.assertEqual(stale["status"], "stale-result")

    def test_approved_gap_body_is_generated_only_from_claims(self):
        evidence = {
            "schema": SCHEMA,
            "version": VERSION,
            "kind": "evidence_packet",
            "packet_id": "gap-evidence",
            "run_id": "run-test",
            "payload": {
                "repository": "project", "worktree": str(self.project), "branch": "main",
                "base_head": self.head, "session_id": "session", "revision": self.head,
                "changed_paths": [], "purpose": "gap_research", "status": "candidate",
                "job_id": "job-00000000000000000000",
                "source_manifest_sha256": "sha256:" + ("a" * 64),
                "question": "What is the cache TTL?", "task_scope": "repository",
                "risk": "objective", "confidence": 0.95, "publication_allowed": True,
                "claims": self.packet()["payload"]["claims"],
                "candidate": {
                    "type": "reference", "title": "Cache TTL", "slug": "cache-ttl",
                    "description": "The repository cache TTL.",
                    "body_markdown": "UNAPPROVED MODEL PROSE",
                },
            },
        }
        evidence_path = self.project / "gap.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        packet = self.packet()
        packet["payload"].update({
            "purpose": "gap_research",
            "evidence_packet_id": "gap-evidence",
            "evidence_packet_path": str(evidence_path),
            "content": "UNAPPROVED REQUEST PROSE",
        })
        output = self.project / "gap-prepared.md"
        self.assertEqual(prepare(packet, output)["status"], "prepared")
        content = output.read_text(encoding="utf-8")
        self.assertIn("The cache TTL is 60 seconds.", content)
        self.assertNotIn("UNAPPROVED", content)


if __name__ == "__main__":
    unittest.main()
