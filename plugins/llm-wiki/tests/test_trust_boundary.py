import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from trust_boundary import END, NOTICE, delimit  # noqa: E402


class TrustBoundaryTests(unittest.TestCase):
    def test_every_malicious_surface_stays_inside_the_data_boundary(self):
        fixture = json.loads(
            (ROOT / "evals" / "fixtures" / "security" / "malicious-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        for kind, value in fixture.items():
            with self.subTest(kind=kind):
                wrapped = delimit(kind, value)
                self.assertTrue(wrapped.startswith(NOTICE))
                self.assertIn(value, wrapped)
                self.assertTrue(wrapped.endswith(END))


if __name__ == "__main__":
    unittest.main()
