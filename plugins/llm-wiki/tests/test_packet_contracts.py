"""Compatibility tests for the shared v1 coprocessor packet contract."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from packet_contracts import (  # noqa: E402
    KINDS,
    MAX_CONTEXT_CAPSULE_BYTES,
    SCHEMA,
    VERSION,
    PacketError,
    canonical_json,
    fingerprint,
    load_packet,
    validate_packet,
)


REQUIRED_PAYLOAD_FIELDS = {
    "candidate_envelope": {"task", "repository", "candidates"},
    "context_capsule": {
        "task",
        "status",
        "claims",
        "relevant_paths",
        "traps",
        "conflicts",
        "verify",
        "gaps",
        "confidence",
    },
    "job_record": {
        "feature",
        "origin",
        "session_id",
        "depth",
        "idempotency_key",
        "budgets",
        "state",
    },
    "evidence_packet": {
        "repository",
        "worktree",
        "branch",
        "base_head",
        "session_id",
        "revision",
        "changed_paths",
    },
    "publication_request": {
        "evidence_packet_id",
        "bundle_root",
        "concept_path",
        "content",
        "expected_head",
        "source_hashes",
        "log_kind",
        "log_message",
    },
}


def _packet(kind: str, payload: dict) -> dict:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "kind": kind,
        "packet_id": f"packet-{kind}",
        "run_id": "run-001",
        "payload": payload,
    }


FIXTURES = {
    "candidate_envelope": _packet(
        "candidate_envelope",
        {"task": "Find the cache policy.", "repository": "llm-wiki", "candidates": []},
    ),
    "context_capsule": _packet(
        "context_capsule",
        {
            "task": "Find the cache policy.",
            "status": "grounded",
            "claims": [],
            "relevant_paths": [],
            "traps": [],
            "conflicts": [],
            "verify": [],
            "gaps": [],
            "confidence": 0.75,
        },
    ),
    "job_record": _packet(
        "job_record",
        {
            "feature": "recall",
            "origin": "user_prompt",
            "session_id": "session-001",
            "depth": 0,
            "idempotency_key": "recall:001",
            "budgets": {"calls": 1, "turns": 8, "seconds": 30, "descendants": 0},
            "state": "pending",
        },
    ),
    "evidence_packet": _packet(
        "evidence_packet",
        {
            "repository": "llm-wiki",
            "worktree": "/work/llm-wiki",
            "branch": "main",
            "base_head": "abc123",
            "session_id": "session-001",
            "revision": "revision-001",
            "changed_paths": [
                {
                    "path": "src/cache.py",
                    "before_sha256": "sha256:before",
                    "after_sha256": "sha256:after",
                    "source": "edit",
                }
            ],
        },
    ),
    "publication_request": _packet(
        "publication_request",
        {
            "evidence_packet_id": "packet-evidence_packet",
            "bundle_root": "/work/llm-wiki/llm-wiki",
            "concept_path": "cache-policy.md",
            "content": "# Cache policy\n",
            "expected_head": "abc123",
            "source_hashes": {"src/cache.py": "sha256:" + ("1" * 64)},
            "log_kind": "Creation",
            "log_message": "Record cache policy.",
        },
    ),
}


def _wrong_type(value):
    if isinstance(value, str):
        return 7
    if isinstance(value, list):
        return {}
    if isinstance(value, dict):
        return []
    if isinstance(value, (int, float)):
        return True
    raise AssertionError(f"fixture has an unsupported test value: {value!r}")


class PacketContractTests(unittest.TestCase):
    def test_all_kinds_validate_and_return_original_mapping(self) -> None:
        self.assertEqual(set(KINDS), set(FIXTURES))
        self.assertTrue(issubclass(PacketError, ValueError))
        for kind, packet in FIXTURES.items():
            with self.subTest(kind=kind):
                self.assertIs(validate_packet(packet), packet)

    def test_expected_kind_is_exact(self) -> None:
        for kind, packet in FIXTURES.items():
            with self.subTest(kind=kind):
                self.assertIs(validate_packet(packet, expected_kind=kind), packet)
                loaded = load_packet(canonical_json(packet), expected_kind=kind)
                self.assertEqual(loaded, packet)
                with self.assertRaises(PacketError):
                    validate_packet(packet, expected_kind="job_record" if kind != "job_record" else "evidence_packet")
        with self.assertRaises(PacketError):
            validate_packet(FIXTURES["job_record"], expected_kind="future_kind")

    def test_malformed_json_non_object_and_bad_common_fields_are_rejected(self) -> None:
        with self.assertRaises(PacketError):
            load_packet('{"schema":')
        for non_object in ([], "packet", 1, None):
            with self.subTest(non_object=non_object):
                with self.assertRaises(PacketError):
                    load_packet(json.dumps(non_object))

        baseline = FIXTURES["candidate_envelope"]
        for field in ("schema", "version", "kind", "packet_id", "run_id", "payload"):
            packet = deepcopy(baseline)
            del packet[field]
            with self.subTest(missing=field):
                with self.assertRaises(PacketError):
                    validate_packet(packet)

        bad_values = {
            "schema": "other.packet",
            "version": True,
            "kind": "future_kind",
            "packet_id": " ",
            "run_id": 12,
            "payload": [],
        }
        for field, value in bad_values.items():
            packet = deepcopy(baseline)
            packet[field] = value
            with self.subTest(wrong=field):
                with self.assertRaises(PacketError):
                    validate_packet(packet)

    def test_kind_required_payload_fields_and_types_are_rejected(self) -> None:
        for kind, required_fields in REQUIRED_PAYLOAD_FIELDS.items():
            for field in required_fields:
                missing = deepcopy(FIXTURES[kind])
                del missing["payload"][field]
                with self.subTest(kind=kind, missing=field):
                    with self.assertRaises(PacketError):
                        validate_packet(missing)

                wrong_type = deepcopy(FIXTURES[kind])
                wrong_type["payload"][field] = _wrong_type(wrong_type["payload"][field])
                with self.subTest(kind=kind, wrong_type=field):
                    with self.assertRaises(PacketError):
                        validate_packet(wrong_type)

    def test_kind_enums_and_numeric_constraints_are_rejected(self) -> None:
        invalid_values = (
            ("context_capsule", "status", "certain"),
            ("context_capsule", "confidence", -0.01),
            ("context_capsule", "confidence", 1.01),
            ("context_capsule", "confidence", float("nan")),
            ("job_record", "state", "done"),
            ("job_record", "depth", -1),
            ("publication_request", "log_kind", "Deletion"),
        )
        for kind, field, value in invalid_values:
            packet = deepcopy(FIXTURES[kind])
            packet["payload"][field] = value
            with self.subTest(kind=kind, field=field, value=value):
                with self.assertRaises(PacketError):
                    validate_packet(packet)

        for field in ("calls", "turns", "seconds", "descendants"):
            for value in (-1, True, None):
                packet = deepcopy(FIXTURES["job_record"])
                packet["payload"]["budgets"][field] = value
                with self.subTest(budget=field, value=value):
                    with self.assertRaises(PacketError):
                        validate_packet(packet)

    def test_unicode_multiline_task_round_trips(self) -> None:
        packet = deepcopy(FIXTURES["candidate_envelope"])
        packet["payload"]["task"] = "追跡する 🔦\nsecond line\nthird line"
        encoded = canonical_json(packet)
        self.assertIn("追跡する", encoded)
        self.assertEqual(load_packet(encoded), packet)

    def test_unknown_fields_are_forward_compatible(self) -> None:
        packet = deepcopy(FIXTURES["context_capsule"])
        packet["trace"] = {"future": True}
        packet["payload"]["future_field"] = ["preserved"]
        self.assertIs(validate_packet(packet), packet)
        self.assertEqual(load_packet(canonical_json(packet)), packet)

    def test_canonical_json_and_fingerprint_ignore_mapping_order(self) -> None:
        packet = deepcopy(FIXTURES["publication_request"])
        reordered = {key: deepcopy(packet[key]) for key in reversed(tuple(packet))}
        payload = packet["payload"]
        reordered["payload"] = {key: deepcopy(payload[key]) for key in reversed(tuple(payload))}

        self.assertEqual(canonical_json(packet), canonical_json(reordered))
        self.assertEqual(fingerprint(packet), fingerprint(reordered))

    def test_evidence_packets_reject_raw_transcript_and_content_keys(self) -> None:
        forbidden = ("content", "file_contents", "raw_content", "raw_transcript", "transcript")
        for key in forbidden:
            packet = deepcopy(FIXTURES["evidence_packet"])
            packet["payload"]["metadata"] = {"nested": {key: "must not cross boundary"}}
            with self.subTest(key=key):
                with self.assertRaises(PacketError):
                    validate_packet(packet)

        packet = deepcopy(FIXTURES["evidence_packet"])
        packet["payload"]["changed_paths"][0]["body"] = "raw file bytes"
        with self.assertRaises(PacketError):
            validate_packet(packet)

    def test_recall_worker_evidence_is_cited_and_has_no_changed_paths(self) -> None:
        packet = deepcopy(FIXTURES["evidence_packet"])
        packet["payload"].update({
            "purpose": "recall_worker",
            "scope": "auth",
            "status": "grounded",
            "claims": [{
                "kind": "answer",
                "text": "Tokens rotate through the key manager.",
                "sources": ["concept:auth/token-rotation.md"],
            }],
            "traps": [],
            "conflicts": [],
            "gaps": [],
            "changed_paths": [],
        })
        self.assertIs(validate_packet(packet, "evidence_packet"), packet)
        packet["payload"]["claims"][0]["sources"] = []
        with self.assertRaises(PacketError):
            validate_packet(packet)

    def test_validate_packet_enforces_the_serialized_size_bound(self) -> None:
        packet = deepcopy(FIXTURES["candidate_envelope"])
        packet["payload"]["task"] = "x" * (256 * 1024)
        with self.assertRaises(PacketError):
            validate_packet(packet)

    def test_context_capsule_enforces_citations_shape_and_budget(self) -> None:
        packet = deepcopy(FIXTURES["context_capsule"])
        packet["payload"]["claims"] = [{
            "kind": "answer",
            "text": "Rotation is coordinated by the key manager.",
            "sources": ["concept:auth/token-rotation.md", "repo:src/keys.py:rotate"],
        }]
        self.assertIs(validate_packet(packet, "context_capsule"), packet)

        for bad_item in (
            {"kind": "answer", "text": "uncited", "sources": []},
            {"kind": "guess", "text": "wrong kind", "sources": ["concept:x.md"]},
            {"kind": "answer", "text": "repo only", "sources": ["repo:x.py:symbol"]},
        ):
            invalid = deepcopy(packet)
            invalid["payload"]["claims"] = [bad_item]
            with self.subTest(item=bad_item):
                with self.assertRaises(PacketError):
                    validate_packet(invalid)

        too_large = deepcopy(packet)
        too_large["payload"]["claims"][0]["text"] = "x" * MAX_CONTEXT_CAPSULE_BYTES
        with self.assertRaises(PacketError):
            validate_packet(too_large)

    def test_structured_gap_proposals_require_insufficient_evidence(self) -> None:
        packet = deepcopy(FIXTURES["context_capsule"])
        packet["payload"].update({
            "status": "insufficient_evidence",
            "gap_proposals": [{
                "question": "How is the feature enabled?",
                "task_scope": "repository",
                "reason": "The supplied concepts omit it.",
                "candidate_paths": ["feature.md"],
            }],
        })
        self.assertIs(validate_packet(packet, "context_capsule"), packet)
        packet["payload"]["status"] = "grounded"
        with self.assertRaises(PacketError):
            validate_packet(packet)

    def test_gap_and_ingest_evidence_extensions_are_bounded(self) -> None:
        gap = deepcopy(FIXTURES["evidence_packet"])
        gap["payload"].update({
            "changed_paths": [],
            "purpose": "gap_research",
            "job_id": "job-00000000000000000000",
            "source_manifest_sha256": "sha256:" + ("b" * 64),
            "status": "candidate",
            "question": "How is the feature enabled?",
            "task_scope": "repository",
            "revision": "abc123",
            "risk": "objective",
            "confidence": 0.9,
            "claims": [{
                "statement": "The feature is enabled.",
                "classification": "observed",
                "scope": "repository",
                "sources": [
                    {"source": "src/feature.py", "source_kind": "code"},
                    {"source": "tests/test_feature.py", "source_kind": "test"},
                ],
            }],
            "candidate": {
                "type": "reference", "title": "Feature", "slug": "feature",
                "description": "Feature behavior.", "body_markdown": "# Feature\n",
            },
        })
        self.assertIs(validate_packet(gap, "evidence_packet"), gap)

        ingest = deepcopy(FIXTURES["evidence_packet"])
        ingest["payload"].update({
            "changed_paths": [],
            "purpose": "ingest_proposal",
            "job_id": "job-11111111111111111111",
            "status": "grounded",
            "scope_id": "ingest-abc",
            "source_manifest_sha256": "sha256:" + ("a" * 64),
            "concepts": [{
                "type": "reference", "title": "Feature", "slug": "feature",
                "description": "Feature behavior.", "body_markdown": "# Feature\n",
                "sources": ["src/feature.py"],
                "claims": [{"statement": "Feature exists."}],
            }],
        })
        self.assertIs(validate_packet(ingest, "evidence_packet"), ingest)


if __name__ == "__main__":
    unittest.main()
