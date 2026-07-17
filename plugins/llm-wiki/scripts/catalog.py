"""Bounded recursive metadata catalog and lexical candidate retrieval for llm-wiki."""

import hashlib
import json
import os
import re

import _hook_common
from packet_contracts import SCHEMA, VERSION, validate_packet
from routing import select_route


MAX_INDEX_FILES = 256
MAX_INDEX_BYTES = 512 * 1024
MAX_ENTRIES = 4096
MAX_CANDIDATES = 12
MAX_ENVELOPE_CHARS = 4500

_BULLET = re.compile(r"^\s*[*-]\s+\[([^\]]+)\]\(([^)]+)\)(?:\s+[—-]\s+(.*))?\s*$")
_TERMS = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset({
    "about", "after", "again", "also", "and", "are", "before", "can", "could", "does",
    "for", "from", "have", "how", "into", "its", "just", "make", "more", "not", "our",
    "please", "should", "that", "the", "their", "then", "this", "through", "use", "using",
    "want", "what", "when", "where", "which", "with", "would", "you", "your",
})


def _terms(value):
    return [term for term in _TERMS.findall(value.lower()) if len(term) >= 3 and term not in _STOP_WORDS]


def _read_bounded(path, remaining):
    with open(path, "rb") as handle:
        raw = handle.read(remaining + 1)
    if len(raw) > remaining:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _entry_from_bullet(line, index_dir, section, bundle_real):
    match = _BULLET.match(line)
    if not match:
        return None
    title, target, description = match.groups()
    if target.endswith("/index.md") or target == "index.md":
        return None
    if "://" in target or target.startswith(("/", "#")):
        return None
    target = target.split("#", 1)[0]
    candidate = os.path.realpath(os.path.join(index_dir, target))
    if not _hook_common.under(candidate, bundle_real) or not candidate.endswith(".md"):
        return None
    relpath = os.path.relpath(candidate, bundle_real).replace(os.sep, "/")
    if os.path.basename(relpath) in ("index.md", "log.md"):
        return None
    return {
        "path": relpath[:512],
        "title": title.strip()[:200],
        "description": (description or "").strip()[:500],
        "section_path": section,
    }


def load_catalog(bundle_root):
    """Read only recursive index files and return bounded concept metadata plus section counts."""
    bundle_real = os.path.realpath(bundle_root)
    entries, seen, sections = [], set(), set()
    index_files = total_bytes = 0
    truncated = False

    if not os.path.isdir(bundle_real):
        return {"entries": [], "sections": [], "truncated": False}

    for current, dirs, files in os.walk(bundle_real, followlinks=False):
        dirs[:] = sorted(
            name for name in dirs
            if name != ".llm-wiki"
            and not os.path.islink(os.path.join(current, name))
            and _hook_common.under(os.path.realpath(os.path.join(current, name)), bundle_real)
        )
        if index_files >= MAX_INDEX_FILES or len(entries) >= MAX_ENTRIES:
            truncated = True
            break
        if "index.md" not in files:
            continue

        section = os.path.relpath(current, bundle_real).replace(os.sep, "/")
        section = "" if section == "." else section
        sections.add(section)
        index_path = os.path.join(current, "index.md")
        remaining = MAX_INDEX_BYTES - total_bytes
        if remaining <= 0:
            truncated = True
            break
        text = _read_bounded(index_path, remaining)
        if text is None:
            truncated = True
            break
        index_files += 1
        total_bytes += len(text.encode("utf-8"))
        for line in text.splitlines():
            entry = _entry_from_bullet(line, current, section, bundle_real)
            if entry is None or entry["path"] in seen:
                continue
            seen.add(entry["path"])
            entries.append(entry)
            if len(entries) >= MAX_ENTRIES:
                truncated = True
                break

    entries.sort(key=lambda item: item["path"])
    section_rows = []
    for section in sorted(sections, key=lambda value: (value.count("/"), value)):
        prefix = section + "/" if section else ""
        direct = sum(1 for entry in entries if entry["section_path"] == section)
        subtree = sum(
            1 for entry in entries
            if not section or entry["section_path"] == section or entry["section_path"].startswith(prefix)
        )
        section_rows.append({"path": section, "direct_count": direct, "subtree_count": subtree})
    return {"entries": entries, "sections": section_rows, "truncated": truncated}


def rank_candidates(catalog, prompt, limit=MAX_CANDIDATES):
    """Return stable lexical matches; title/path/section evidence outweighs descriptions."""
    query_terms = set(_terms(prompt))
    if not query_terms:
        return []
    normalized_prompt = " ".join(_TERMS.findall(prompt.lower()))
    ranked = []
    for entry in catalog["entries"]:
        title = " ".join(_TERMS.findall(entry["title"].lower()))
        path = " ".join(_TERMS.findall(entry["path"].lower()))
        section = " ".join(_TERMS.findall(entry["section_path"].lower()))
        title_terms = set(_terms(entry["title"]))
        path_terms = set(_terms(entry["path"]))
        section_terms = set(_terms(entry["section_path"]))
        description_terms = set(_terms(entry["description"]))
        score = (
            8 * len(query_terms & title_terms)
            + 7 * len(query_terms & path_terms)
            + 6 * len(query_terms & section_terms)
            + 2 * len(query_terms & description_terms)
        )
        if title and title in normalized_prompt:
            score += 24
        if path and path in normalized_prompt:
            score += 20
        if section and section in normalized_prompt:
            score += 16
        if score:
            ranked.append({**entry, "score": score})
    ranked.sort(key=lambda item: (-item["score"], item["path"]))
    return ranked[:max(0, min(limit, MAX_CANDIDATES))]


def candidate_envelope(catalog, prompt, project, session_id=None, bundle_root=None, run_id=None):
    """Build a valid, bounded v1 candidate packet for model-facing hook injection."""
    candidates = rank_candidates(catalog, prompt)
    if not candidates:
        return None
    task = prompt.strip()[:512] or "(empty prompt)"
    repository = os.path.basename(os.path.realpath(project)) or "repository"
    digest_input = task + "\n" + "\n".join(item["path"] for item in candidates)
    packet = {
        "schema": SCHEMA,
        "version": VERSION,
        "kind": "candidate_envelope",
        "packet_id": "candidate-" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:16],
        "run_id": str(run_id or session_id or "sessionless")[:200],
        "payload": {
            "task": task,
            "repository": repository,
            "bundle_root": os.path.realpath(bundle_root or os.path.join(project, "llm-wiki")),
            "candidates": [],
            "catalog_truncated": bool(catalog["truncated"]),
        },
    }
    for candidate in candidates:
        packet["payload"]["candidates"].append(candidate)
        if len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) > MAX_ENVELOPE_CHARS:
            packet["payload"]["candidates"].pop()
            break
    if not packet["payload"]["candidates"]:
        return None
    packet["payload"]["routing"] = select_route(prompt, packet["payload"]["candidates"])
    while (
        len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) > MAX_ENVELOPE_CHARS
        and packet["payload"]["candidates"]
    ):
        packet["payload"]["candidates"].pop()
        packet["payload"]["routing"] = select_route(prompt, packet["payload"]["candidates"])
    if not packet["payload"]["candidates"]:
        return None
    validate_packet(packet, "candidate_envelope")
    return packet


def render_catalog(catalog, descriptions=True):
    """Render a recursive human-readable map from metadata only."""
    lines = []
    section_counts = {row["path"]: row for row in catalog["sections"]}
    for section in catalog["sections"]:
        label = section["path"] or "root"
        lines.append(
            "## %s (%d direct / %d total)" %
            (label, section["direct_count"], section["subtree_count"])
        )
        for entry in catalog["entries"]:
            if entry["section_path"] != section["path"]:
                continue
            line = "* [%s](llm-wiki/%s)" % (entry["title"], entry["path"])
            if descriptions and entry["description"]:
                line += " — " + entry["description"]
            lines.append(line)
        lines.append("")
    if not section_counts:
        lines.append("_No indexed concepts yet._")
    if catalog["truncated"]:
        lines.append("_Catalog truncated at deterministic safety limits._")
    return "\n".join(lines).rstrip()
