#!/usr/bin/env python3
"""Run LLM Wiki's deterministic, model-free compatibility gate."""

import argparse
from pathlib import Path
import sys
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="run offline hook and storage compatibility fixtures",
    )
    args = parser.parse_args()
    if not args.deterministic:
        parser.error("choose --deterministic")

    suite = unittest.defaultTestLoader.discover(
        str(PLUGIN_ROOT / "tests"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
