"""Compatibility fixtures for the deterministic storage boundary."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_OPS = ROOT / "scripts" / "bundle_ops.py"
DOCTOR = ROOT / "scripts" / "doctor.py"


class StorageSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.bundle = self.root / "llm-wiki"

    def _apply(self, draft, *, kind="Creation"):
        content_file = self.root / "draft.md"
        content_file.write_text(draft, encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(BUNDLE_OPS),
                "apply",
                str(self.bundle),
                "--concept",
                "runtime-foundation.md",
                "--content-file",
                str(content_file),
                "--log-kind",
                kind,
                "--log-message",
                "Recorded the runtime foundation fixture.",
                "--date",
                "2026-07-16",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_apply_initializes_and_doctor_validates_bundle(self):
        result = self._apply(
            """---
type: reference
title: Runtime foundation
description: Frozen storage compatibility fixture.
tags:
  - runtime
timestamp: 2026-07-16T00:00:00Z
---
# Runtime foundation

The deterministic apply boundary remains available during migration.
"""
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "applied")
        self.assertTrue((self.bundle / "runtime-foundation.md").is_file())
        self.assertTrue((self.bundle / "index.md").is_file())
        self.assertTrue((self.bundle / "log.md").is_file())

        doctor = subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                str(self.bundle),
                "--mode",
                "strict",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertEqual(json.loads(doctor.stdout)["summary"]["errors"], 0)

    def test_secret_block_leaves_existing_concept_unchanged(self):
        initial = """---
type: reference
---
# Safe concept

No credentials are stored here.
"""
        first = self._apply(initial)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.bundle / "runtime-foundation.md").read_bytes()

        fake_named_key = "AKIA" + ("A" * 16)
        blocked = self._apply(
            """---
type: reference
---
# Unsafe concept

Credential-shaped test value: %s
""" % fake_named_key,
            kind="Update",
        )

        self.assertEqual(blocked.returncode, 1, blocked.stderr)
        self.assertEqual(json.loads(blocked.stdout)["status"], "blocked:secret")
        self.assertEqual((self.bundle / "runtime-foundation.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
