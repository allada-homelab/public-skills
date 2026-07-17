"""Structured claim/evidence provenance and worktree freshness for Wiki-managed concepts."""

from datetime import datetime
import hashlib
import json
import os
import re


VERSION = 1
HEADING = "## Wiki provenance"
_BLOCK = re.compile(r"^## Wiki provenance\s*\n```json\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL)
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_CLASSIFICATIONS = frozenset({"observed", "inferred", "contested"})
_OBJECTIVE_KINDS = frozenset({"code", "test", "doc", "git"})
_SOURCE_KINDS = _OBJECTIVE_KINDS | frozenset({"wiki", "model"})


class ProvenanceError(ValueError):
    pass


def _stable_id(prefix, *values):
    raw = "\0".join(str(value).strip() for value in values)
    return prefix + "-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def claim_id(statement, scope):
    return _stable_id("claim", statement, scope)


def evidence_id(source, content_sha256, repository_head, scope):
    return _stable_id("evidence", source, content_sha256, repository_head, scope)


def file_fingerprint(project, source):
    path = str(source).split(":", 1)[0]
    candidate = os.path.realpath(os.path.join(project, path))
    project_real = os.path.realpath(project)
    try:
        if os.path.commonpath([project_real, candidate]) != project_real or not os.path.isfile(candidate):
            return None
    except ValueError:
        return None
    digest = hashlib.sha256()
    try:
        with open(candidate, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return "sha256:" + digest.hexdigest()


def extract(text):
    match = _BLOCK.search(text)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ProvenanceError("Wiki provenance block is not valid JSON: %s" % exc) from exc
    return value


def render(document):
    validate(document)
    return "%s\n```json\n%s\n```" % (
        HEADING,
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2),
    )


def strip(text):
    """Remove an existing Wiki provenance block before deterministic restamping."""
    return _BLOCK.sub("", text).rstrip() + "\n"


def _nonempty(value, path, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append("%s must be a non-empty string" % path)


def _timestamp(value, path, errors):
    _nonempty(value, path, errors)
    if not isinstance(value, str):
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("%s must be ISO-8601" % path)


def validation_errors(document):
    if not isinstance(document, dict):
        return ["provenance must be a JSON object"]
    errors = []
    if document.get("version") != VERSION:
        errors.append("version must be %d" % VERSION)
    claims = document.get("claims")
    evidence = document.get("evidence")
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claims = []
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
        evidence = []

    evidence_by_id = {}
    for index, item in enumerate(evidence):
        path = "evidence[%d]" % index
        if not isinstance(item, dict):
            errors.append("%s must be an object" % path)
            continue
        for field in (
            "id", "source", "content_sha256", "repository_head", "scope", "producer", "model",
            "plugin_version",
        ):
            _nonempty(item.get(field), "%s.%s" % (path, field), errors)
        _timestamp(item.get("captured_at"), "%s.captured_at" % path, errors)
        if item.get("expires_at") is not None:
            _timestamp(item.get("expires_at"), "%s.expires_at" % path, errors)
        if item.get("source_kind") not in _SOURCE_KINDS:
            errors.append("%s.source_kind is unsupported" % path)
        if isinstance(item.get("content_sha256"), str) and not _HASH.match(item["content_sha256"]):
            errors.append("%s.content_sha256 must be sha256:<64 lowercase hex>" % path)
        expected = evidence_id(
            item.get("source", ""), item.get("content_sha256", ""),
            item.get("repository_head", ""), item.get("scope", ""),
        )
        if item.get("id") != expected:
            errors.append("%s.id does not match its stable evidence ID" % path)
        derived = item.get("derived_from", [])
        if not isinstance(derived, list) or any(not isinstance(value, str) or not value for value in derived):
            errors.append("%s.derived_from must be a string list" % path)
        if isinstance(item.get("id"), str):
            if item["id"] in evidence_by_id:
                errors.append("duplicate evidence ID: %s" % item["id"])
            evidence_by_id[item["id"]] = item

    for index, item in enumerate(claims):
        path = "claims[%d]" % index
        if not isinstance(item, dict):
            errors.append("%s must be an object" % path)
            continue
        for field in ("id", "statement", "scope"):
            _nonempty(item.get(field), "%s.%s" % (path, field), errors)
        if item.get("classification") not in _CLASSIFICATIONS:
            errors.append("%s.classification is unsupported" % path)
        expected = claim_id(item.get("statement", ""), item.get("scope", ""))
        if item.get("id") != expected:
            errors.append("%s.id does not match its stable claim ID" % path)
        refs = item.get("evidence_ids")
        if not isinstance(refs, list) or not refs:
            errors.append("%s.evidence_ids must be a non-empty list" % path)
        elif any(ref not in evidence_by_id for ref in refs):
            errors.append("%s references missing evidence" % path)

    def has_objective_root(item_id, stack):
        if item_id in stack:
            errors.append("evidence lineage cycle: %s" % " -> ".join(stack + [item_id]))
            return False
        item = evidence_by_id.get(item_id)
        if item is None:
            return False
        if item.get("source_kind") in _OBJECTIVE_KINDS:
            return True
        parents = item.get("derived_from", [])
        return any(has_objective_root(parent, stack + [item_id]) for parent in parents)

    for item in evidence:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        parents = item.get("derived_from", [])
        if not isinstance(parents, list):
            continue
        for parent in parents:
            if parent == item_id:
                errors.append("evidence cannot cite itself: %s" % item_id)
            elif parent not in evidence_by_id:
                errors.append("evidence %s references missing parent %s" % (item_id, parent))
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        refs = claim.get("evidence_ids", [])
        if isinstance(refs, list) and refs and not any(has_objective_root(ref, []) for ref in refs):
            errors.append("claims[%d] has no objective evidence root" % index)
    return sorted(set(errors))


def validate(document):
    errors = validation_errors(document)
    if errors:
        raise ProvenanceError("; ".join(errors))
    return document


def freshness(document, project):
    """Return evidence ID -> fresh|stale|unknown using current worktree bytes, including dirty edits."""
    validate(document)
    result = {}
    for item in document["evidence"]:
        if item["source_kind"] not in _OBJECTIVE_KINDS or item["source_kind"] == "git":
            result[item["id"]] = "unknown"
            continue
        current = file_fingerprint(project, item["source"])
        result[item["id"]] = "fresh" if current == item["content_sha256"] else (
            "stale" if current is not None else "unknown"
        )
    return result
