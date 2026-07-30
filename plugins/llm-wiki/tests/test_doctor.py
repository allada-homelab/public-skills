"""Doctor conformance tests — OKF v0.2 frontmatter grammar, trust families, legacy migration.

The v0.2 families (§5) are written as flow mappings (`generated: { by, at }`), block lists of
mappings (`sources:`), and nested block mappings — none of which the v0.1 restricted grammar
accepted. These tests pin both the grammar and the rule severities.
"""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from doctor import (  # noqa: E402
    NONE,
    OK,
    UNPARSEABLE,
    check_concept,
    check_root_index,
    parse_frontmatter,
)

ACTOR = "llm-wiki/claude-opus-5"


def concept(*frontmatter_lines, body="# Body\n"):
    """A concept whose frontmatter is the given lines, with a valid `type`."""
    lines = ("type: reference",) + frontmatter_lines
    return "---\n%s\n---\n\n%s" % ("\n".join(lines), body)


def parsed(*frontmatter_lines):
    """The parsed frontmatter dict for the given lines (asserts it parsed)."""
    status, data = parse_frontmatter(concept(*frontmatter_lines))
    assert status == OK, "expected parseable frontmatter, got %r" % status
    return data


def findings(text, relpath="c.md", checker=check_concept):
    out = []
    checker(text, relpath, out)
    return out


def rules(text, severity, checker=check_concept):
    return sorted({f["rule"] for f in findings(text, checker=checker) if f["severity"] == severity})


def errors(text, checker=check_concept):
    return rules(text, "ERROR", checker)


def warnings(text, checker=check_concept):
    return rules(text, "WARNING", checker)


class FrontmatterGrammarTests(unittest.TestCase):
    """§5/§10 shapes the v0.1 restricted grammar rejected outright."""

    def test_flow_mapping_value_parses_to_a_dict(self):
        data = parsed("generated: { by: %s, at: 2026-07-29T21:45:00Z }" % ACTOR)
        self.assertEqual(data["generated"], {"by": ACTOR, "at": "2026-07-29T21:45:00Z"})

    def test_flow_sequence_value_parses_to_a_list(self):
        self.assertEqual(parsed("tags: [sales, revenue]")["tags"], ["sales", "revenue"])

    def test_block_list_of_flow_mappings_parses(self):
        data = parsed(
            "verified:",
            "  - { by: human:davidallada, at: 2026-07-29T09:00:00Z }",
            "  - { by: process:llm-wiki-verifier, at: 2026-07-29T10:00:00Z }",
        )
        self.assertEqual(
            data["verified"],
            [
                {"by": "human:davidallada", "at": "2026-07-29T09:00:00Z"},
                {"by": "process:llm-wiki-verifier", "at": "2026-07-29T10:00:00Z"},
            ],
        )

    def test_block_list_of_block_mappings_parses(self):
        data = parsed(
            "sources:",
            "  - id: ga4-schema",
            "    resource: https://example.com/schema",
            "    usage_count: 5000",
            "  - id: policy",
            "    resource: /references/policy.md",
        )
        self.assertEqual(
            data["sources"],
            [
                {
                    "id": "ga4-schema",
                    "resource": "https://example.com/schema",
                    "usage_count": "5000",
                },
                {"id": "policy", "resource": "/references/policy.md"},
            ],
        )

    def test_nested_block_mapping_parses(self):
        data = parsed("generated:", "  by: %s" % ACTOR, "  at: 2026-07-29T21:45:00Z")
        self.assertEqual(data["generated"], {"by": ACTOR, "at": "2026-07-29T21:45:00Z"})

    def test_nested_flow_mapping_inside_a_flow_mapping_parses(self):
        data = parsed("usage_window: { from: 2026-06-01, to: 2026-06-30 }")
        self.assertEqual(data["usage_window"], {"from": "2026-06-01", "to": "2026-06-30"})

    def test_scalar_and_simple_block_list_still_parse(self):
        data = parsed("title: Orders", "tags:", "  - sales", "  - revenue")
        self.assertEqual(data["title"], "Orders")
        self.assertEqual(data["tags"], ["sales", "revenue"])

    def test_inline_comment_is_stripped_from_a_plain_scalar(self):
        self.assertEqual(parsed("status: stable   # default")["status"], "stable")

    def test_colon_bearing_scalar_survives_flow_parsing(self):
        data = parsed("verified: { by: human:davidallada, at: 2026-07-29T21:45:00Z }")
        self.assertEqual(data["verified"]["by"], "human:davidallada")

    def test_quoted_flow_scalar_keeps_its_commas(self):
        data = parsed('generated: { by: "a, b", at: 2026-07-29T21:45:00Z }')
        self.assertEqual(data["generated"]["by"], "a, b")

    def test_tab_indentation_is_unparseable(self):
        status, _ = parse_frontmatter("---\ntype: reference\n\tby: x\n---\n")
        self.assertEqual(status, UNPARSEABLE)

    def test_unterminated_flow_mapping_is_unparseable(self):
        status, _ = parse_frontmatter("---\ngenerated: { by: x\n---\n")
        self.assertEqual(status, UNPARSEABLE)

    def test_missing_frontmatter_block_is_none(self):
        status, _ = parse_frontmatter("# Just a body\n")
        self.assertEqual(status, NONE)


class TrustFamilyTests(unittest.TestCase):
    """R8: a v0.2 family that is PRESENT must be well-shaped; absence is never an error (§11)."""

    def test_bare_type_only_concept_has_no_findings(self):
        self.assertEqual(errors(concept()), [])

    def test_well_formed_families_produce_no_errors(self):
        text = concept(
            "status: stable",
            "stale_after: 2026-12-31",
            "generated: { by: %s, at: 2026-07-29T21:45:00Z }" % ACTOR,
            "verified:",
            "  - { by: process:llm-wiki-verifier, at: 2026-07-29T22:00:00Z }",
            "sources:",
            "  - id: doctor",
            "    resource: plugins/llm-wiki/scripts/doctor.py",
            "    last_modified: 2026-07-29",
        )
        self.assertEqual(errors(text), [])

    def test_generated_without_by_is_an_error(self):
        self.assertIn("R8", errors(concept("generated: { at: 2026-07-29T21:45:00Z }")))

    def test_generated_with_non_iso_at_is_an_error(self):
        self.assertIn("R8", errors(concept("generated: { by: %s, at: yesterday }" % ACTOR)))

    def test_actor_violating_the_convention_is_an_error(self):
        self.assertIn("R8", errors(concept("generated: { by: someone, at: 2026-07-29T21:45:00Z }")))

    def test_human_and_process_actor_prefixes_are_accepted(self):
        for actor in ("human:davidallada", "process:llm-wiki-verifier", "agent/model-1"):
            with self.subTest(actor=actor):
                text = concept("generated: { by: %s, at: 2026-07-29T21:45:00Z }" % actor)
                self.assertEqual(errors(text), [])

    def test_bare_verified_mapping_is_accepted_as_one_element(self):
        text = concept("verified: { by: %s, at: 2026-07-29T21:45:00Z }" % ACTOR)
        self.assertEqual(errors(text), [])

    def test_verified_entry_missing_at_is_an_error(self):
        self.assertIn("R8", errors(concept("verified: { by: %s }" % ACTOR)))

    def test_unknown_status_value_is_an_error(self):
        self.assertIn("R8", errors(concept("status: archived")))

    def test_each_documented_status_value_is_accepted(self):
        for value in ("draft", "stable", "deprecated"):
            with self.subTest(status=value):
                self.assertEqual(errors(concept("status: %s" % value)), [])

    def test_stale_after_must_be_a_plain_date(self):
        self.assertIn("R8", errors(concept("stale_after: 2026-12-31T00:00:00Z")))

    def test_sources_entry_without_resource_is_an_error(self):
        self.assertIn("R8", errors(concept("sources:", "  - id: orphan")))

    def test_duplicate_source_ids_are_an_error(self):
        text = concept(
            "sources:",
            "  - id: dup",
            "    resource: https://example.com/a",
            "  - id: dup",
            "    resource: https://example.com/b",
        )
        self.assertIn("R8", errors(text))

    def test_footnote_without_a_matching_source_id_warns(self):
        text = concept(
            "sources:",
            "  - id: known",
            "    resource: https://example.com/a",
            body="A claim.[^unknown]\n\n[^unknown]: dangling\n",
        )
        self.assertIn("R8", warnings(text))

    def test_footnote_matching_a_source_id_does_not_warn(self):
        text = concept(
            "sources:",
            "  - id: known",
            "    resource: https://example.com/a",
            body="A claim.[^known]\n\n[^known]: GA4 schema\n",
        )
        self.assertEqual(warnings(text), [])


class LegacyMigrationTests(unittest.TestCase):
    """R9: v0.1 fields are tolerated with a WARNING so installed bundles keep validating (§13.1)."""

    def test_legacy_timestamp_warns_and_never_errors(self):
        text = concept("timestamp: 2026-07-29T21:45:00Z")
        self.assertEqual(errors(text), [])
        self.assertIn("R9", warnings(text))

    def test_legacy_scalar_verified_warns_and_never_errors(self):
        text = concept("verified: 2026-07-29T21:45:00Z")
        self.assertEqual(errors(text), [])
        self.assertIn("R9", warnings(text))

    def test_legacy_citations_body_section_warns(self):
        text = concept(body="# Citations\n\n[1] [Something](https://example.com)\n")
        self.assertEqual(errors(text), [])
        self.assertIn("R9", warnings(text))

    def test_body_finding_reports_a_file_relative_line_number(self):
        # `type: reference` + the two `---` fences occupy lines 1-3, then a blank line, so the
        # heading is file line 5. A body-relative number here would point a reader at line 1.
        text = concept(body="# Citations\n")
        citation = next(f for f in findings(text) if f["rule"] == "R9")
        self.assertEqual(text.split("\n")[citation["line"] - 1], "# Citations")

    def test_v02_generated_alongside_no_legacy_field_is_clean(self):
        text = concept("generated: { by: %s, at: 2026-07-29T21:45:00Z }" % ACTOR)
        self.assertEqual(warnings(text), [])


class RootIndexVersionTests(unittest.TestCase):
    def test_current_version_is_accepted(self):
        self.assertEqual(errors('---\nokf_version: "0.2"\n---\n# Wiki\n', checker=check_root_index), [])

    def test_legacy_version_warns_but_does_not_error(self):
        text = '---\nokf_version: "0.1"\n---\n# Wiki\n'
        self.assertEqual(errors(text, checker=check_root_index), [])
        self.assertIn("R9", warnings(text, checker=check_root_index))

    def test_unknown_version_is_an_error(self):
        self.assertIn("R3b", errors('---\nokf_version: "0.3"\n---\n# Wiki\n', checker=check_root_index))

    def test_unquoted_version_is_an_error(self):
        self.assertIn("R3b", errors("---\nokf_version: 0.2\n---\n# Wiki\n", checker=check_root_index))

    def test_extra_key_is_an_error(self):
        text = '---\nokf_version: "0.2"\ntitle: Wiki\n---\n# Wiki\n'
        self.assertIn("R3b", errors(text, checker=check_root_index))


if __name__ == "__main__":
    unittest.main()
