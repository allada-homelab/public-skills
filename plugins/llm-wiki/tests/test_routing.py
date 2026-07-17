import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from routing import select_route  # noqa: E402


class RoutingCorpusTests(unittest.TestCase):
    def test_labelled_corpus_meets_route_and_lens_gates(self):
        corpus = json.loads(
            (ROOT / "evals" / "fixtures" / "routing-corpus.json").read_text(encoding="utf-8")
        )
        route_hits = lens_hits = direct_archaeologist = 0
        for case in corpus:
            result = select_route(case["prompt"], case["candidates"])
            route_hits += result["route"] == case["route"]
            lens_hits += result["lens"] == case["lens"]
            if case.get("direct") and result["route"] == "archaeologist":
                direct_archaeologist += 1
            self.assertIn(result["skill"], (
                "/llm-wiki:recall-glimmer",
                "/llm-wiki:recall",
                "/llm-wiki:recall-archaeologist",
            ))
        self.assertGreaterEqual(route_hits / len(corpus), 0.90)
        self.assertGreaterEqual(lens_hits / len(corpus), 0.85)
        self.assertEqual(direct_archaeologist, 0)


if __name__ == "__main__":
    unittest.main()
