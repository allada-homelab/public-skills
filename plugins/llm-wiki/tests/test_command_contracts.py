"""Frozen public-command invariants retained while internals are strangled."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicCommandContractTests(unittest.TestCase):
    def test_query_remains_cited_read_only_and_gap_aware(self):
        query = (ROOT / "commands" / "query.md").read_text(encoding="utf-8")
        self.assertIn("Sources:", query)
        self.assertIn("GAP:", query)
        self.assertIn("subagent_type: llm-wiki:wiki-verifier", query)
        self.assertIn("/llm-wiki:recall", query)
        self.assertIn("context_capsule", query)
        self.assertIn("query never writes a concept", query)
        self.assertNotIn("access.log", query)
        self.assertNotIn("allowed-tools: Write", query)
        self.assertNotIn("allowed-tools: Edit", query)

    def test_capture_remains_one_concept_upsert_through_gated_apply(self):
        capture = (ROOT / "commands" / "capture.md").read_text(encoding="utf-8")
        self.assertIn("one conformant OKF concept", capture)
        self.assertIn("create-or-edit", capture)
        self.assertIn("bundle_ops.py\" apply", capture)
        self.assertIn("Doctor-gates", capture)
        self.assertIn("secret-scans", capture)
        self.assertIn("`apply` owns staging", capture)


if __name__ == "__main__":
    unittest.main()
