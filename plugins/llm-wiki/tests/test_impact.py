from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from impact import build_reverse_map, match_impacts  # noqa: E402


class ImpactMapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bundle = Path(self._tmp.name) / "llm-wiki"
        self.bundle.mkdir()
        (self.bundle / "auth-policy.md").write_text(
            "---\ntype: reference\n---\n# Auth policy\n\n## Verify\n- src/auth/token.py:rotate — rotation entry point\n",
            encoding="utf-8",
        )
        (self.bundle / "deploy.md").write_text(
            "---\ntype: runbook\n---\n# Deploy\n\nSee [auth policy](./auth-policy.md).\n",
            encoding="utf-8",
        )

    def test_direct_anchor_and_transitive_chain_are_preserved(self):
        reverse = build_reverse_map(self.bundle)
        findings = match_impacts(reverse, [{"path": "src/auth/token.py"}])
        direct = next(item for item in findings if item["concept"] == "auth-policy.md")
        transitive = next(item for item in findings if item["concept"] == "deploy.md")
        self.assertEqual(direct["edge_kind"], "verify")
        self.assertTrue(direct["surface"])
        self.assertEqual(
            transitive["chain"], ["src/auth/token.py", "auth-policy.md", "deploy.md"]
        )
        self.assertFalse(transitive["surface"])

    def test_no_match_is_silent(self):
        self.assertEqual(
            match_impacts(build_reverse_map(self.bundle), [{"path": "src/unrelated.py"}]), []
        )


if __name__ == "__main__":
    unittest.main()
