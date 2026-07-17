import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import candidate_envelope, load_catalog, rank_candidates  # noqa: E402
from packet_contracts import validate_packet  # noqa: E402


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bundle = Path(self._tmp.name) / "llm-wiki"
        auth = self.bundle / "auth"
        auth.mkdir(parents=True)
        (self.bundle / "index.md").write_text(
            '# Wiki\n\n## Concepts\n\n* [Deploy guide](./deploy.md) — Authentication release steps.\n\n'
            "## Sections\n\n* [Auth](./auth/index.md)\n",
            encoding="utf-8",
        )
        (auth / "index.md").write_text(
            "# Auth\n\n## Concepts\n\n"
            "* [Token rotation](./token-rotation.md) — Rotate signing keys safely.\n"
            "* [Session cookies](./session-cookies.md) — Cookie validation rules.\n",
            encoding="utf-8",
        )

    def test_recursive_catalog_counts_without_reading_concept_bodies(self):
        catalog = load_catalog(self.bundle)
        self.assertEqual(
            [entry["path"] for entry in catalog["entries"]],
            ["auth/session-cookies.md", "auth/token-rotation.md", "deploy.md"],
        )
        counts = {section["path"]: section for section in catalog["sections"]}
        self.assertEqual(counts[""]["direct_count"], 1)
        self.assertEqual(counts[""]["subtree_count"], 3)
        self.assertEqual(counts["auth"]["direct_count"], 2)

    def test_title_and_path_matches_outrank_description_only(self):
        ranked = rank_candidates(load_catalog(self.bundle), "token rotation authentication")
        self.assertEqual(ranked[0]["path"], "auth/token-rotation.md")
        self.assertGreater(ranked[0]["score"], ranked[-1]["score"])

    def test_candidate_packet_is_valid_and_bounded(self):
        packet = candidate_envelope(
            load_catalog(self.bundle), "How does token rotation work?", self.bundle.parent, "session-a"
        )
        self.assertIsNotNone(packet)
        validate_packet(packet, "candidate_envelope")
        self.assertLessEqual(
            len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))), 6000
        )


if __name__ == "__main__":
    unittest.main()
