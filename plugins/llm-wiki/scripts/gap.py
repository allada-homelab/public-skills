"""Deterministic scheduling, scoping, and publication policy for gap research."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unicodedata

import _hook_common
from packet_contracts import PacketError, load_packet, validate_packet
from provenance import file_fingerprint


MAX_GAP_PROPOSALS = 2
MAX_MANIFEST_PATHS = 256
_SOURCE_EXTENSIONS = frozenset({
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js", ".json", ".jsx",
    ".kt", ".kts", ".md", ".php", ".proto", ".py", ".rb", ".rs", ".scala", ".sh",
    ".sql", ".swift", ".toml", ".ts", ".tsx", ".yaml", ".yml",
})
_SKIP_DIRS = frozenset({
    ".claude", ".codex", ".git", ".hg", ".svn", ".llm-wiki", ".venv", "__pycache__", "build", "coverage",
    "dist", "node_modules", "target", "vendor",
})
_SENSITIVE_NAMES = frozenset({
    ".env", "credentials", "credentials.json", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa",
})
_RISKY = re.compile(
    r"\b(auth(?:entication|orization)?|credential|secret|token|password|permission|security|"
    r"privacy|compliance|legal|policy|intent|production|deploy(?:ment)?)\b",
    re.IGNORECASE,
)


def normalize_text(value):
    """Normalize model phrasing for revision-scoped idempotency."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(text.split())


def proposal_key(question, task_scope, revision):
    normalized = "%s\0%s\0%s" % (
        str(revision), normalize_text(question), normalize_text(task_scope)
    )
    return "gap:%s:%s" % (
        str(revision)[:40], hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    )


def current_head(project):
    try:
        proc = subprocess.run(
            ["git", "-C", project, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unborn"
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unborn"


def _safe_source(project, path):
    if not isinstance(path, str) or not path or os.path.isabs(path):
        return False
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or ".." in parts or any(part in _SKIP_DIRS for part in parts):
        return False
    name = parts[-1].lower()
    if (
        name in _SENSITIVE_NAMES
        or name.startswith(".env.")
        or name.endswith((".key", ".p12", ".pfx", ".pem"))
    ):
        return False
    real = os.path.realpath(os.path.join(project, normalized))
    bundle = os.path.realpath(_hook_common.bundle_root(project))
    return (
        _hook_common.under(real, os.path.realpath(project))
        and not _hook_common.under(real, bundle)
        and os.path.isfile(real)
    )


def source_manifest(project, preferred_paths=()):
    """Build a bounded exact-path manifest; researchers never need broad filesystem search."""
    project = os.path.realpath(project)
    preferred = []
    for value in preferred_paths:
        if _safe_source(project, value):
            preferred.append(value.replace("\\", "/"))
    paths = set(preferred)
    for root, dirs, files in os.walk(project, followlinks=False):
        dirs[:] = sorted(
            name for name in dirs
            if name not in _SKIP_DIRS
            and not os.path.islink(os.path.join(root, name))
            and not _hook_common.under(
                os.path.realpath(os.path.join(root, name)),
                os.path.realpath(_hook_common.bundle_root(project)),
            )
        )
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), project).replace(os.sep, "/")
            if os.path.splitext(name)[1].lower() not in _SOURCE_EXTENSIONS:
                continue
            if _safe_source(project, rel):
                paths.add(rel)
            if len(paths) >= MAX_MANIFEST_PATHS:
                break
        if len(paths) >= MAX_MANIFEST_PATHS:
            break
    return sorted(paths, key=lambda value: (value not in preferred, value))[:MAX_MANIFEST_PATHS]


def _packet_candidates(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _packet_candidates(child)
    elif isinstance(value, list):
        for child in value:
            yield from _packet_candidates(child)


def extract_packet(value, expected_kind):
    """Find the one exact packet returned inside a Claude tool-response wrapper."""
    found = []
    for text in _packet_candidates(value):
        try:
            packet = load_packet(text.strip(), expected_kind)
        except (PacketError, UnicodeError):
            continue
        found.append(packet)
    unique = {json.dumps(item, sort_keys=True, separators=(",", ":")): item for item in found}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _actual_source_kind(path):
    normalized = path.replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    if normalized.startswith("tests/") or "/tests/" in normalized or name.startswith("test_") or ".test." in name:
        return "test"
    if normalized.startswith("docs/") or name.endswith(".md"):
        return "doc"
    return "code"


def publication_policy(project, packet, allowed_sources=None):
    """Return a fail-closed eligibility decision and code-computed source hashes."""
    try:
        validate_packet(packet, "evidence_packet")
    except PacketError as exc:
        return {"allowed": False, "reason": "invalid research packet: %s" % exc}
    payload = packet["payload"]
    if payload.get("purpose") != "gap_research" or payload.get("status") != "candidate":
        return {"allowed": False, "reason": "research did not produce a candidate"}
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or confidence < 0.85:
        return {"allowed": False, "reason": "confidence is below the autonomous threshold"}
    if payload.get("risk") != "objective":
        return {"allowed": False, "reason": "only objective repository facts auto-publish"}
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"allowed": False, "reason": "candidate has no claims"}
    candidate = payload.get("candidate", {})
    risky_text = " ".join(
        [payload.get("question", ""), payload.get("task_scope", "")]
        + [str(claim.get("statement", "")) for claim in claims if isinstance(claim, dict)]
        + [str(candidate.get(field, "")) for field in ("title", "description", "body_markdown")]
    )
    if _RISKY.search(risky_text):
        return {"allowed": False, "reason": "high-risk topic requires human evidence review"}
    if current_head(project) != payload.get("revision"):
        return {"allowed": False, "reason": "repository revision changed"}

    allowed_real = None
    if allowed_sources is not None:
        allowed_real = {os.path.realpath(os.path.join(project, path)) for path in allowed_sources}
    else:
        return {"allowed": False, "reason": "issued source manifest is missing"}
    source_hashes = {}
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("classification") != "observed":
            return {"allowed": False, "reason": "every claim must be directly observed"}
        sources = claim.get("sources")
        if not isinstance(sources, list):
            return {"allowed": False, "reason": "claim sources are missing"}
        distinct, kinds = set(), set()
        for source in sources:
            if not isinstance(source, dict):
                return {"allowed": False, "reason": "claim source is malformed"}
            path, kind = source.get("source"), source.get("source_kind")
            real = os.path.realpath(os.path.join(project, str(path)))
            actual_kind = _actual_source_kind(str(path))
            if (
                kind != actual_kind
                or not _safe_source(project, path)
                or real not in allowed_real
            ):
                return {"allowed": False, "reason": "claim source is not safe objective evidence"}
            canonical = os.path.relpath(real, os.path.realpath(project)).replace(os.sep, "/")
            distinct.add(real)
            kinds.add(actual_kind)
            source_hashes[canonical] = file_fingerprint(project, canonical)
        if len(distinct) < 2 or not {"code", "test"}.issubset(kinds):
            return {"allowed": False, "reason": "claims require independent code and test evidence"}
    return {"allowed": True, "reason": "objective code-and-test evidence", "source_hashes": source_hashes}


def store_result(project, session_id, job_id, packet, decision):
    """Persist an immutable ignored result; quarantined records omit drafted concept bodies."""
    root = os.path.join(
        _hook_common.session_state_dir(project, session_id), "gap-candidates"
    )
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "%s.json" % job_id)
    payload = packet["payload"]
    if decision["allowed"]:
        record = {
            **packet,
            "payload": {
                **payload,
                "publication_allowed": True,
                "policy_reason": decision["reason"],
            },
        }
    else:
        record = {
            "job_id": job_id,
            "run_id": packet["run_id"],
            "publication_allowed": False,
            "decision_reason": decision["reason"],
            "question": payload.get("question"),
            "task_scope": payload.get("task_scope"),
            "revision": payload.get("revision"),
            "risk": payload.get("risk"),
            "confidence": payload.get("confidence"),
            "claims": payload.get("claims", []),
        }
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except FileExistsError:
        pass
    return path
