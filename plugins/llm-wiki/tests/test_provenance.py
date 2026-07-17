from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from doctor import check_concept  # noqa: E402
from provenance import (  # noqa: E402
    claim_id,
    evidence_id,
    file_fingerprint,
    freshness,
    render,
    validation_errors,
)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        source = self.project / "src" / "rules.py"
        source.parent.mkdir()
        source.write_text("MODE = 'safe'\n", encoding="utf-8")
        digest = file_fingerprint(self.project, "src/rules.py:MODE")
        evidence = evidence_id("src/rules.py:MODE", digest, "head-123", "repository")
        statement = "The repository defaults to safe mode."
        self.document = {
            "version": 1,
            "claims": [{
                "id": claim_id(statement, "repository"),
                "statement": statement,
                "classification": "observed",
                "scope": "repository",
                "evidence_ids": [evidence],
            }],
            "evidence": [{
                "id": evidence,
                "source_kind": "code",
                "source": "src/rules.py:MODE",
                "content_sha256": digest,
                "repository_head": "head-123",
                "scope": "repository",
                "producer": "wiki-scribe",
                "model": "sonnet",
                "plugin_version": "0.1.0",
                "captured_at": "2026-07-16T12:00:00Z",
                "derived_from": [],
            }],
        }

    def test_managed_concept_is_doctor_gated_and_dirty_edits_go_stale(self):
        body = "---\ntype: reference\nwiki_managed: true\n---\n# Safe mode\n\n" + render(self.document)
        findings = []
        check_concept(body, "safe-mode.md", findings)
        self.assertEqual([item for item in findings if item["rule"] == "R6"], [])
        self.assertEqual(set(freshness(self.document, self.project).values()), {"fresh"})

        (self.project / "src" / "rules.py").write_text("MODE = 'fast'\n", encoding="utf-8")
        self.assertEqual(set(freshness(self.document, self.project).values()), {"stale"})

        missing = []
        check_concept("---\ntype: reference\nwiki_managed: true\n---\n# Missing\n", "missing.md", missing)
        self.assertTrue(any(item["rule"] == "R6" for item in missing))

    def test_model_only_and_self_referential_lineage_are_rejected(self):
        evidence = self.document["evidence"][0]
        evidence["source_kind"] = "model"
        evidence["derived_from"] = [evidence["id"]]
        errors = validation_errors(self.document)
        self.assertTrue(any("cannot cite itself" in error for error in errors))
        self.assertTrue(any("no objective evidence root" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
