"""v0.1 -> v0.2 legacy-field migration (§13.1), applied in place by `bundle_ops apply`."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bundle_ops import (  # noqa: E402
    MIGRATION_ACTOR,
    migrate_legacy_frontmatter,
    stamp_generated_if_absent,
)
from doctor import OK, parse_frontmatter  # noqa: E402


def concept(*frontmatter_lines, body="# Body\n\nProse.\n"):
    lines = ("type: gotcha", "title: A thing") + frontmatter_lines
    return "---\n%s\n---\n\n%s" % ("\n".join(lines), body)


def migrated(*frontmatter_lines, body="# Body\n\nProse.\n"):
    text, changed = migrate_legacy_frontmatter(concept(*frontmatter_lines, body=body))
    status, data = parse_frontmatter(text)
    assert status == OK, "migrated output must stay parseable"
    return text, data, changed


class MigrationTests(unittest.TestCase):
    def test_timestamp_becomes_generated_with_the_same_instant(self):
        _text, data, changed = migrated("timestamp: 2026-07-02T10:00:00Z")
        self.assertTrue(changed)
        self.assertEqual(data["generated"], {"by": MIGRATION_ACTOR, "at": "2026-07-02T10:00:00Z"})
        self.assertNotIn("timestamp", data)

    def test_scalar_verified_becomes_a_by_at_mapping(self):
        _text, data, changed = migrated("verified: 2026-07-17T00:00:00Z")
        self.assertTrue(changed)
        self.assertEqual(data["verified"], {"by": MIGRATION_ACTOR, "at": "2026-07-17T00:00:00Z"})

    def test_date_only_legacy_value_is_preserved_verbatim(self):
        _text, data, _changed = migrated("timestamp: 2026-07-02")
        self.assertEqual(data["generated"]["at"], "2026-07-02")

    def test_already_v02_concept_is_untouched(self):
        original = concept("generated: { by: llm-wiki/claude-opus-5, at: 2026-07-02T10:00:00Z }")
        text, changed = migrate_legacy_frontmatter(original)
        self.assertFalse(changed)
        self.assertEqual(text, original)

    def test_existing_generated_wins_over_a_legacy_timestamp(self):
        _text, data, changed = migrated(
            "timestamp: 2020-01-01T00:00:00Z",
            "generated: { by: llm-wiki/claude-opus-5, at: 2026-07-02T10:00:00Z }",
        )
        self.assertTrue(changed)
        self.assertEqual(data["generated"]["at"], "2026-07-02T10:00:00Z")
        self.assertNotIn("timestamp", data)

    def test_other_frontmatter_and_body_are_preserved_byte_for_byte(self):
        body = "# Body\n\nA line mentioning timestamp: 2020-01-01 inside prose.\n"
        text, data, _changed = migrated("tags:", "  - one", "timestamp: 2026-07-02", body=body)
        self.assertEqual(data["tags"], ["one"])
        self.assertEqual(data["title"], "A thing")
        self.assertTrue(text.endswith(body))

    def test_nested_timestamp_key_is_not_migrated(self):
        _text, data, changed = migrated("sources:", "  - resource: x", "    timestamp: 2026-07-02")
        self.assertFalse(changed)
        self.assertEqual(data["sources"], [{"resource": "x", "timestamp": "2026-07-02"}])

    def test_migrated_concept_passes_the_doctor_with_no_legacy_warning(self):
        from doctor import check_concept

        text, _data, _changed = migrated("timestamp: 2026-07-02", "verified: 2026-07-17")
        findings = []
        check_concept(text, "c.md", findings)
        self.assertEqual([f for f in findings if f["rule"] in ("R8", "R9")], [])


class GeneratedStampTests(unittest.TestCase):
    """Every write goes through the apply engine, so that is where `generated` is guaranteed."""

    AT = "2026-07-29T21:45:00Z"
    ACTOR = "llm-wiki/claude-opus-5"

    def test_absent_generated_is_stamped(self):
        text = stamp_generated_if_absent(concept(), self.ACTOR, self.AT)
        _status, data = parse_frontmatter(text)
        self.assertEqual(data["generated"], {"by": self.ACTOR, "at": self.AT})

    def test_existing_generated_is_never_overwritten(self):
        original = concept("generated: { by: llm-wiki/sonnet, at: 2026-01-01T00:00:00Z }")
        self.assertEqual(stamp_generated_if_absent(original, self.ACTOR, self.AT), original)

    def test_stamping_preserves_body_and_other_keys(self):
        text = stamp_generated_if_absent(concept("tags:", "  - one"), self.ACTOR, self.AT)
        _status, data = parse_frontmatter(text)
        self.assertEqual(data["tags"], ["one"])
        self.assertTrue(text.endswith("# Body\n\nProse.\n"))

    def test_content_without_frontmatter_is_left_alone(self):
        self.assertEqual(stamp_generated_if_absent("# No frontmatter\n", self.ACTOR, self.AT),
                         "# No frontmatter\n")


if __name__ == "__main__":
    unittest.main()
