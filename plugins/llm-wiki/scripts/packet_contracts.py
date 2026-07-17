"""Versioned JSON packet contracts shared by llm-wiki coprocessor surfaces.

The validator is intentionally small and stdlib-only. It freezes the cross-agent envelope and the
minimum payload shape while accepting unknown fields so later tickets can extend v1 additively.
"""

from collections.abc import Mapping
import hashlib
import json
import math
import re


SCHEMA = "llm-wiki.packet"
VERSION = 1
MAX_PACKET_BYTES = 256 * 1024
MAX_CONTEXT_CAPSULE_BYTES = 4000

KINDS = frozenset({
    "candidate_envelope",
    "context_capsule",
    "job_record",
    "evidence_packet",
    "publication_request",
})

_PAYLOAD_FIELDS = {
    "candidate_envelope": {
        "task": str,
        "repository": str,
        "candidates": list,
    },
    "context_capsule": {
        "task": str,
        "status": str,
        "claims": list,
        "relevant_paths": list,
        "traps": list,
        "conflicts": list,
        "verify": list,
        "gaps": list,
        "confidence": (int, float),
    },
    "job_record": {
        "feature": str,
        "origin": str,
        "session_id": str,
        "depth": int,
        "idempotency_key": str,
        "budgets": Mapping,
        "state": str,
    },
    "evidence_packet": {
        "repository": str,
        "worktree": str,
        "branch": str,
        "base_head": str,
        "session_id": str,
        "revision": str,
        "changed_paths": list,
    },
    "publication_request": {
        "evidence_packet_id": str,
        "bundle_root": str,
        "concept_path": str,
        "content": str,
        "expected_head": str,
        "source_hashes": Mapping,
        "log_kind": str,
        "log_message": str,
    },
}

_CAPSULE_STATES = frozenset({"grounded", "insufficient_evidence"})
_JOB_STATES = frozenset({
    "pending",
    "running",
    "completed",
    "blocked",
    "failed",
    "cancelled",
    "stale",
})
_LOG_KINDS = frozenset({"Creation", "Update"})
_CAPSULE_LIST_LIMITS = {
    "claims": 6,
    "relevant_paths": 8,
    "traps": 4,
    "conflicts": 4,
    "verify": 4,
    "gaps": 4,
}
_CLAIM_KINDS = frozenset({"answer", "invariant"})
_CONFLICT_KINDS = frozenset({"conflict", "omission"})
_ROUTES = frozenset({"glimmer", "oracle", "archaeologist"})
_LENSES = frozenset({"implementer", "debugger", "reviewer", "operator", "newcomer", "historian", "neutral"})
_BUDGET_FIELDS = ("calls", "turns", "seconds", "descendants")
_EVIDENCE_FORBIDDEN_KEYS = frozenset({
    "content",
    "file_contents",
    "raw_content",
    "raw_transcript",
    "transcript",
})
_CHANGED_PATH_FIELDS = frozenset({"path", "before_sha256", "after_sha256", "source"})
_CHANGED_PATH_SOURCES = frozenset({"write", "edit", "git_delta"})
_GAP_RISKS = frozenset({
    "objective", "policy", "intent", "security", "production_behavior", "unknown"
})


class PacketError(ValueError):
    """The packet is malformed or violates its declared v1 contract."""


def _is_instance(value, expected):
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == (int, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected)


def _require_nonempty_string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise PacketError("%s must be a non-empty string" % path)


def _forbidden_keys(value, forbidden):
    """Return forbidden mapping keys found anywhere in a JSON-shaped value."""
    found = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in forbidden:
                found.add(key)
            found.update(_forbidden_keys(child, forbidden))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child, forbidden))
    return found


def _validate_sources_item(item, path, kinds=None):
    if not isinstance(item, Mapping):
        raise PacketError("%s must be a JSON object" % path)
    _require_nonempty_string(item.get("text"), "%s.text" % path)
    sources = item.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PacketError("%s.sources must be a non-empty list" % path)
    for index, source in enumerate(sources):
        _require_nonempty_string(source, "%s.sources[%d]" % (path, index))
    if not any(source.startswith("concept:") for source in sources):
        raise PacketError("%s.sources must include a concept: citation" % path)
    if kinds is not None and item.get("kind") not in kinds:
        raise PacketError("%s.kind is not supported" % path)
    if "classification" in item and item["classification"] not in ("observed", "inferred", "contested"):
        raise PacketError("%s.classification is unsupported" % path)
    if "scope" in item:
        _require_nonempty_string(item["scope"], "%s.scope" % path)
    if "freshness" in item and item["freshness"] not in ("fresh", "stale", "unknown"):
        raise PacketError("%s.freshness is unsupported" % path)
    if "confidence" in item:
        value = item["confidence"]
        if not _is_instance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 1:
            raise PacketError("%s.confidence must be between 0 and 1" % path)


def _validate_common(packet, expected_kind):
    if not isinstance(packet, Mapping):
        raise PacketError("packet must be a JSON object")
    if packet.get("schema") != SCHEMA:
        raise PacketError("schema must be %s" % SCHEMA)
    if packet.get("version") != VERSION or isinstance(packet.get("version"), bool):
        raise PacketError("version must be %d" % VERSION)

    kind = packet.get("kind")
    if kind not in KINDS:
        raise PacketError("kind must be one of: %s" % ", ".join(sorted(KINDS)))
    if expected_kind is not None:
        if expected_kind not in KINDS:
            raise PacketError("unknown expected kind: %s" % expected_kind)
        if kind != expected_kind:
            raise PacketError("expected %s, got %s" % (expected_kind, kind))

    _require_nonempty_string(packet.get("packet_id"), "packet_id")
    _require_nonempty_string(packet.get("run_id"), "run_id")
    if not isinstance(packet.get("payload"), Mapping):
        raise PacketError("payload must be a JSON object")
    return kind, packet["payload"]


def _validate_payload(kind, payload):
    for field, expected in _PAYLOAD_FIELDS[kind].items():
        if field not in payload:
            raise PacketError("payload.%s is required for %s" % (field, kind))
        if not _is_instance(payload[field], expected):
            raise PacketError("payload.%s has the wrong type" % field)
        if expected is str:
            _require_nonempty_string(payload[field], "payload.%s" % field)

    if kind == "context_capsule":
        if payload["status"] not in _CAPSULE_STATES:
            raise PacketError("payload.status is not a context capsule state")
        confidence = payload["confidence"]
        if not math.isfinite(confidence) or confidence < 0 or confidence > 1:
            raise PacketError("payload.confidence must be between 0 and 1")
        for field, limit in _CAPSULE_LIST_LIMITS.items():
            if len(payload[field]) > limit:
                raise PacketError("payload.%s exceeds its %d-item limit" % (field, limit))
        for index, item in enumerate(payload["claims"]):
            _validate_sources_item(item, "payload.claims[%d]" % index, _CLAIM_KINDS)
            if payload["status"] == "insufficient_evidence" and item["kind"] == "answer":
                raise PacketError("insufficient_evidence capsules cannot contain answer claims")
        for index, item in enumerate(payload["traps"]):
            _validate_sources_item(item, "payload.traps[%d]" % index)
        for index, item in enumerate(payload["conflicts"]):
            _validate_sources_item(item, "payload.conflicts[%d]" % index, _CONFLICT_KINDS)
        for field in ("relevant_paths", "verify", "gaps"):
            for index, value in enumerate(payload[field]):
                _require_nonempty_string(value, "payload.%s[%d]" % (field, index))
        if "route" in payload and payload["route"] not in _ROUTES:
            raise PacketError("payload.route is not supported")
        if "lens" in payload and payload["lens"] not in _LENSES:
            raise PacketError("payload.lens is not supported")
        if "route_reason" in payload:
            _require_nonempty_string(payload["route_reason"], "payload.route_reason")
        if "gap_proposals" in payload:
            proposals = payload["gap_proposals"]
            if not isinstance(proposals, list) or len(proposals) > 1:
                raise PacketError("payload.gap_proposals must be a list of at most 1 item")
            if proposals and payload["status"] != "insufficient_evidence":
                raise PacketError("only insufficient_evidence capsules may propose gap research")
            for index, proposal in enumerate(proposals):
                path = "payload.gap_proposals[%d]" % index
                if not isinstance(proposal, Mapping):
                    raise PacketError("%s must be a JSON object" % path)
                for field in ("question", "task_scope", "reason"):
                    _require_nonempty_string(proposal.get(field), "%s.%s" % (path, field))
                candidates = proposal.get("candidate_paths")
                if not isinstance(candidates, list) or len(candidates) > 12:
                    raise PacketError("%s.candidate_paths must be a list of at most 12 items" % path)
                for candidate_index, candidate in enumerate(candidates):
                    _require_nonempty_string(
                        candidate, "%s.candidate_paths[%d]" % (path, candidate_index)
                    )

    elif kind == "job_record":
        if payload["state"] not in _JOB_STATES:
            raise PacketError("payload.state is not a job state")
        if payload["depth"] < 0:
            raise PacketError("payload.depth must be non-negative")
        for field in _BUDGET_FIELDS:
            value = payload["budgets"].get(field)
            if not _is_instance(value, int) or value < 0:
                raise PacketError("payload.budgets.%s must be a non-negative integer" % field)
        parent_id = payload.get("parent_id")
        if parent_id is not None:
            _require_nonempty_string(parent_id, "payload.parent_id")

    elif kind == "evidence_packet":
        forbidden = _forbidden_keys(payload, _EVIDENCE_FORBIDDEN_KEYS)
        if forbidden:
            raise PacketError(
                "evidence packets cannot contain raw content keys: %s"
                % ", ".join(sorted(forbidden))
            )
        for index, changed in enumerate(payload["changed_paths"]):
            path = "payload.changed_paths[%d]" % index
            if not isinstance(changed, Mapping):
                raise PacketError("%s must be a JSON object" % path)
            unknown = set(changed) - _CHANGED_PATH_FIELDS
            if unknown:
                raise PacketError(
                    "%s has unsupported fields: %s" % (path, ", ".join(sorted(unknown)))
                )
            _require_nonempty_string(changed.get("path"), "%s.path" % path)
            if changed.get("source") not in _CHANGED_PATH_SOURCES:
                raise PacketError("%s.source is not a changed-path source" % path)
            for hash_field in ("before_sha256", "after_sha256"):
                value = changed.get(hash_field)
                if value is not None:
                    _require_nonempty_string(value, "%s.%s" % (path, hash_field))
            if changed.get("before_sha256") is None and changed.get("after_sha256") is None:
                raise PacketError("%s must carry a before or after hash" % path)
        if payload.get("purpose") == "recall_worker":
            _require_nonempty_string(payload.get("scope"), "payload.scope")
            if payload.get("status") not in _CAPSULE_STATES:
                raise PacketError("payload.status is not a worker evidence state")
            if payload["changed_paths"]:
                raise PacketError("recall worker evidence cannot carry changed paths")
            for field in ("claims", "traps", "conflicts"):
                values = payload.get(field)
                if not isinstance(values, list):
                    raise PacketError("payload.%s must be a list" % field)
                for index, item in enumerate(values):
                    kinds = (
                        _CLAIM_KINDS if field == "claims"
                        else (_CONFLICT_KINDS if field == "conflicts" else None)
                    )
                    _validate_sources_item(item, "payload.%s[%d]" % (field, index), kinds)
            gaps = payload.get("gaps")
            if not isinstance(gaps, list):
                raise PacketError("payload.gaps must be a list")
            for index, value in enumerate(gaps):
                _require_nonempty_string(value, "payload.gaps[%d]" % index)
        elif payload.get("purpose") == "gap_research":
            if payload["changed_paths"]:
                raise PacketError("gap research evidence cannot carry changed paths")
            if payload.get("status") not in ("candidate", "insufficient_evidence"):
                raise PacketError("payload.status is not a gap research state")
            for field in ("question", "task_scope", "revision"):
                _require_nonempty_string(payload.get(field), "payload.%s" % field)
            _require_nonempty_string(payload.get("job_id"), "payload.job_id")
            digest = payload.get("source_manifest_sha256")
            if not isinstance(digest, str) or not re.match(r"^sha256:[0-9a-f]{64}$", digest):
                raise PacketError("payload.source_manifest_sha256 must be a sha256 fingerprint")
            if payload.get("risk") not in _GAP_RISKS:
                raise PacketError("payload.risk is not a supported gap risk")
            confidence = payload.get("confidence")
            if (
                not _is_instance(confidence, (int, float))
                or not math.isfinite(confidence)
                or confidence < 0
                or confidence > 1
            ):
                raise PacketError("payload.confidence must be between 0 and 1")
            claims = payload.get("claims")
            if not isinstance(claims, list):
                raise PacketError("payload.claims must be a list")
            if payload["status"] == "candidate" and not claims:
                raise PacketError("candidate gap research must include claims")
            for index, claim in enumerate(claims):
                path = "payload.claims[%d]" % index
                if not isinstance(claim, Mapping):
                    raise PacketError("%s must be a JSON object" % path)
                for field in ("statement", "scope"):
                    _require_nonempty_string(claim.get(field), "%s.%s" % (path, field))
                if claim.get("classification") not in ("observed", "inferred", "contested"):
                    raise PacketError("%s.classification is unsupported" % path)
                sources = claim.get("sources")
                if not isinstance(sources, list) or not sources:
                    raise PacketError("%s.sources must be a non-empty list" % path)
                for source_index, source in enumerate(sources):
                    source_path = "%s.sources[%d]" % (path, source_index)
                    if not isinstance(source, Mapping):
                        raise PacketError("%s must be a JSON object" % source_path)
                    _require_nonempty_string(source.get("source"), "%s.source" % source_path)
                    if source.get("source_kind") not in ("code", "test", "doc"):
                        raise PacketError("%s.source_kind is not objective repository evidence" % source_path)
            candidate = payload.get("candidate")
            if payload["status"] == "candidate":
                if not isinstance(candidate, Mapping):
                    raise PacketError("payload.candidate must be a JSON object")
                for field in ("type", "title", "slug", "description", "body_markdown"):
                    _require_nonempty_string(candidate.get(field), "payload.candidate.%s" % field)
        elif payload.get("purpose") == "ingest_proposal":
            if payload["changed_paths"]:
                raise PacketError("ingest proposal evidence cannot carry changed paths")
            if payload.get("status") not in _CAPSULE_STATES:
                raise PacketError("payload.status is not an ingest proposal state")
            _require_nonempty_string(payload.get("scope_id"), "payload.scope_id")
            _require_nonempty_string(payload.get("job_id"), "payload.job_id")
            digest = payload.get("source_manifest_sha256")
            if not isinstance(digest, str) or not re.match(r"^sha256:[0-9a-f]{64}$", digest):
                raise PacketError("payload.source_manifest_sha256 must be a sha256 fingerprint")
            concepts = payload.get("concepts")
            if not isinstance(concepts, list) or len(concepts) > 40:
                raise PacketError("payload.concepts must be a list of at most 40 items")
            for index, concept in enumerate(concepts):
                path = "payload.concepts[%d]" % index
                if not isinstance(concept, Mapping):
                    raise PacketError("%s must be a JSON object" % path)
                for field in ("type", "title", "slug", "description", "body_markdown"):
                    _require_nonempty_string(concept.get(field), "%s.%s" % (path, field))
                sources = concept.get("sources")
                if not isinstance(sources, list) or not sources:
                    raise PacketError("%s.sources must be a non-empty list" % path)
                for source_index, source in enumerate(sources):
                    _require_nonempty_string(source, "%s.sources[%d]" % (path, source_index))
                claims = concept.get("claims")
                if not isinstance(claims, list) or not claims:
                    raise PacketError("%s.claims must be a non-empty list" % path)

    elif kind == "publication_request" and payload["log_kind"] not in _LOG_KINDS:
        raise PacketError("payload.log_kind must be Creation or Update")
    elif kind == "publication_request":
        if "claims" in payload:
            if not isinstance(payload["claims"], list) or not payload["claims"]:
                raise PacketError("payload.claims must be a non-empty list")
            for index, claim in enumerate(payload["claims"]):
                path = "payload.claims[%d]" % index
                if not isinstance(claim, Mapping):
                    raise PacketError("%s must be a JSON object" % path)
                _require_nonempty_string(claim.get("statement"), "%s.statement" % path)
                _require_nonempty_string(claim.get("scope"), "%s.scope" % path)
                if claim.get("classification") not in ("observed", "inferred", "contested"):
                    raise PacketError("%s.classification is unsupported" % path)
                sources = claim.get("sources")
                if not isinstance(sources, list) or not sources:
                    raise PacketError("%s.sources must be a non-empty list" % path)
                for source_index, source in enumerate(sources):
                    source_path = "%s.sources[%d]" % (path, source_index)
                    if not isinstance(source, Mapping):
                        raise PacketError("%s must be a JSON object" % source_path)
                    _require_nonempty_string(source.get("source"), "%s.source" % source_path)
                    if source.get("source_kind") not in ("code", "test", "doc", "git"):
                        raise PacketError("%s.source_kind is not objective" % source_path)
        for source, digest in payload["source_hashes"].items():
            _require_nonempty_string(source, "payload.source_hashes key")
            if not isinstance(digest, str) or not re.match(r"^sha256:[0-9a-f]{64}$", digest):
                raise PacketError("payload.source_hashes values must be sha256 fingerprints")


def validate_packet(packet, expected_kind=None):
    """Validate one packet without mutating it; unknown fields are forward-compatible."""
    kind, payload = _validate_common(packet, expected_kind)
    _validate_payload(kind, payload)
    encoded = _encode(packet)
    if kind == "context_capsule" and len(encoded.encode("utf-8")) > MAX_CONTEXT_CAPSULE_BYTES:
        raise PacketError("context capsule exceeds %d bytes" % MAX_CONTEXT_CAPSULE_BYTES)
    return packet


def _encode(packet):
    try:
        text = json.dumps(
            packet,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PacketError("packet is not finite JSON: %s" % exc) from exc
    if len(text.encode("utf-8")) > MAX_PACKET_BYTES:
        raise PacketError("packet exceeds %d bytes" % MAX_PACKET_BYTES)
    return text


def canonical_json(packet):
    """Return stable UTF-8 JSON for hashing, transport, and immutable fixture comparisons."""
    validate_packet(packet)
    return _encode(packet)


def fingerprint(packet):
    """Content fingerprint for dedupe/idempotency; not an authorization primitive."""
    return hashlib.sha256(canonical_json(packet).encode("utf-8")).hexdigest()


def load_packet(text, expected_kind=None):
    """Parse and validate one bounded JSON packet."""
    if not isinstance(text, (str, bytes, bytearray)):
        raise PacketError("packet input must be text or bytes")
    raw = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    if len(raw) > MAX_PACKET_BYTES:
        raise PacketError("packet exceeds %d bytes" % MAX_PACKET_BYTES)
    try:
        packet = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError("packet is not valid JSON: %s" % exc) from exc
    return validate_packet(packet, expected_kind)
