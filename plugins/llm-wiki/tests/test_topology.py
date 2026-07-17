from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from topology import dedupe_proposals, plan_ingest_scopes, select_section  # noqa: E402
from ingest_plan import plan  # noqa: E402
from job_state import JobController  # noqa: E402


class TopologyTests(unittest.TestCase):
    def test_explicit_unique_longest_and_ambiguous_placement(self):
        sections = ["backend", "backend/payments", "frontend"]
        self.assertEqual(select_section(sections, ["src/anything.py"], "chosen"), "chosen")
        self.assertEqual(
            select_section(sections, ["backend/payments/api.py"]), "backend/payments"
        )
        self.assertEqual(
            select_section(sections, ["backend/api.py", "frontend/app.ts"]), ""
        )
        self.assertEqual(select_section([], ["src/app.py"]), "")

    def test_ingest_scopes_are_disjoint_bounded_and_sensitive_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            for rel in ("backend/a.py", "frontend/a.ts", "docs/guide.md", "tools/x.py"):
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=x\n", encoding="utf-8")
            bundle = repo / "llm-wiki"
            bundle.mkdir()
            (bundle / "index.md").write_text("# Wiki\n", encoding="utf-8")
            units = plan_ingest_scopes(repo, "high", bundle)
            self.assertLessEqual(len(units), 3)
            manifests = [set(unit["source_manifest"]) for unit in units]
            for index, manifest in enumerate(manifests):
                self.assertNotIn(".env", manifest)
                self.assertFalse(any(path.startswith("llm-wiki/") for path in manifest))
                for other in manifests[index + 1:]:
                    self.assertTrue(manifest.isdisjoint(other))

    def test_dedupe_names_dropped_identities(self):
        proposals = [
            {"slug": "auth", "title": "Auth"},
            {"slug": "auth", "title": "Auth duplicate"},
            {"slug": "cache", "title": "Cache"},
        ]
        result = dedupe_proposals(proposals, [{"path": "existing.md", "title": "Existing"}])
        self.assertEqual([item["slug"] for item in result["accepted"]], ["auth", "cache"])
        self.assertEqual(len(result["dropped"]), 1)

    def test_subdirectory_ingest_jobs_use_project_controller_and_exact_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            repo = project / "backend" / "foo"
            repo.mkdir(parents=True)
            source = repo / "app.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            bundle = project / "llm-wiki"
            bundle.mkdir()
            (bundle / "index.md").write_text("# Wiki\n", encoding="utf-8")
            result = plan(repo, bundle, "min", "session", "foo", project)
            self.assertEqual(len(result["workers"]), 1)
            job_id = result["workers"][0]["job"]["packet_id"]
            stored = JobController(project, "session").get(job_id)
            self.assertEqual(
                stored["payload"]["authorization"]["read_paths"], [str(source.resolve())]
            )


if __name__ == "__main__":
    unittest.main()
