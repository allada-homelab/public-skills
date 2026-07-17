import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from batch_publication import prepare_batch  # noqa: E402
from provenance import file_fingerprint  # noqa: E402


BUNDLE_OPS = ROOT / "scripts" / "bundle_ops.py"


class BatchPublicationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        (self.project / "src").mkdir(parents=True)
        (self.project / "tests").mkdir()
        (self.project / "src" / "feature.py").write_text("ENABLED = True\n", encoding="utf-8")
        (self.project / "tests" / "test_feature.py").write_text("assert True\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "src", "tests"], cwd=self.project, check=True)
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
               "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.project, env=env, check=True)
        self.head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.project, text=True
        ).strip()
        self.bundle = self.project / "llm-wiki"
        self.source_hashes = {
            path: file_fingerprint(self.project, path)
            for path in ("src/feature.py", "tests/test_feature.py")
        }

    def value(self):
        sources = [
            {"source": "src/feature.py", "source_kind": "code"},
            {"source": "tests/test_feature.py", "source_kind": "test"},
        ]
        return {
            "project": str(self.project),
            "bundle_root": str(self.bundle),
            "expected_head": self.head,
            "source_manifest": [item["source"] for item in sources],
            "expected_source_hashes": self.source_hashes,
            "into": "features",
            "run_id": "run-ingest",
            "concepts": [{
                "type": "reference",
                "title": "Feature enablement",
                "slug": "feature-enablement",
                "description": "How the feature is enabled.",
                "body_markdown": "# Feature enablement\n\nThe repository enables this feature.",
                "claims": [{
                    "statement": "The repository enables this feature.",
                    "classification": "observed",
                    "scope": "feature",
                    "sources": sources,
                }],
            }],
        }

    def test_prepare_and_single_batch_apply(self):
        output = self.project / "prepared.json"
        result = prepare_batch(self.value(), output)
        self.assertEqual(result["status"], "prepared")
        manifest = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("## Wiki provenance", manifest["concepts"][0]["content"])
        applied = subprocess.run(
            [sys.executable, str(BUNDLE_OPS), "batch-apply", str(self.bundle),
             "--manifest", str(output), "--date", "2026-07-16"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(json.loads(applied.stdout)["status"], "applied")
        self.assertTrue((self.bundle / "features" / "feature-enablement.md").is_file())
        log = (self.bundle / "log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("Ingested 1 grounded concept"), 1)

    def test_source_drift_is_stale_and_secret_batch_is_blocked(self):
        prepared_path = self.project / "prepared-before-drift.json"
        self.assertEqual(prepare_batch(self.value(), prepared_path)["status"], "prepared")
        (self.project / "src" / "feature.py").write_text("ENABLED = False\n", encoding="utf-8")
        late_stale = subprocess.run(
            [sys.executable, str(BUNDLE_OPS), "batch-apply", str(self.bundle),
             "--manifest", str(prepared_path), "--date", "2026-07-16"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(late_stale.returncode, 3, late_stale.stderr)
        self.assertEqual(json.loads(late_stale.stdout)["status"], "stale-result")
        self.assertFalse((self.bundle / "features" / "feature-enablement.md").exists())
        stale = prepare_batch(self.value(), self.project / "stale.json")
        self.assertEqual(stale["status"], "stale-result")

        manifest = self.project / "unsafe.json"
        fake_key = "AKIA" + ("A" * 16)
        manifest.write_text(json.dumps({
            "project": str(self.project),
            "expected_head": self.head,
            "expected_source_hashes": {},
            "expected_destinations": {"unsafe.md": None},
            "log_message": "Unsafe fixture.",
            "concepts": [{
                "path": "unsafe.md",
                "content": "---\ntype: reference\n---\n# Unsafe\n\n%s\n" % fake_key,
            }],
        }), encoding="utf-8")
        blocked = subprocess.run(
            [sys.executable, str(BUNDLE_OPS), "batch-apply", str(self.bundle),
             "--manifest", str(manifest), "--date", "2026-07-16"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(blocked.returncode, 1, blocked.stderr)
        self.assertEqual(json.loads(blocked.stdout)["status"], "blocked:secret")
        self.assertFalse((self.bundle / "unsafe.md").exists())

    def test_destination_created_after_prepare_is_not_overwritten(self):
        output = self.project / "prepared.json"
        self.assertEqual(prepare_batch(self.value(), output)["status"], "prepared")
        destination = self.bundle / "features" / "feature-enablement.md"
        destination.parent.mkdir(parents=True)
        destination.write_text("concurrent capture\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(BUNDLE_OPS), "batch-apply", str(self.bundle),
             "--manifest", str(output), "--date", "2026-07-16"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), "concurrent capture\n")


if __name__ == "__main__":
    unittest.main()
