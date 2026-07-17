"""Deterministic monorepo section selection, bounded ingest scopes, and proposal dedupe."""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import re
import sys

import _hook_common


_TOKENS = re.compile(r"[a-z0-9]+")
_SECTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$")
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", ".llm-wiki", ".venv", "__pycache__", "build", "coverage",
    "dist", "node_modules", "target", "vendor",
})
_SENSITIVE = frozenset({
    ".env", "credentials", "credentials.json", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa",
})
_SCOPE_WORKERS = {"min": 1, "medium": 2, "high": 3}
_SCOPE_CONCEPTS = {"min": 4, "medium": 15, "high": 40}
MAX_FILES_PER_UNIT = 256


def _file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_section(value):
    """Return a normalized safe bundle-relative section or raise ValueError."""
    section = str(value or "").strip().replace("\\", "/").strip("/")
    if not section or not _SECTION.fullmatch(section):
        raise ValueError("section must be a safe non-empty bundle-relative path")
    if any(part in (".", "..", ".llm-wiki") for part in section.split("/")):
        raise ValueError("section contains a reserved path segment")
    return section


def _token_sequence(value):
    return tuple(_TOKENS.findall(str(value).lower()))


def _contains(sequence, needle):
    if not needle or len(needle) > len(sequence):
        return False
    return any(sequence[index:index + len(needle)] == needle for index in range(len(sequence) - len(needle) + 1))


def select_section(existing_sections, evidence_paths, explicit=None):
    """Explicit placement wins; otherwise a unique longest section-token match wins."""
    if explicit is not None:
        return validate_section(explicit)
    evidence = [_token_sequence(path) for path in evidence_paths if str(path).strip()]
    matches = []
    for section in sorted(set(existing_sections)):
        if not section:
            continue
        tokens = _token_sequence(section)
        if tokens and any(_contains(path_tokens, tokens) for path_tokens in evidence):
            matches.append((len(tokens), section))
    if not matches:
        return ""
    longest = max(score for score, _section in matches)
    winners = [section for score, section in matches if score == longest]
    return winners[0] if len(winners) == 1 else ""


def _safe_file(repo, path, bundle):
    rel = os.path.relpath(path, repo).replace(os.sep, "/")
    parts = rel.split("/")
    name = parts[-1].lower()
    real = os.path.realpath(path)
    return (
        _hook_common.under(real, repo)
        and not _hook_common.under(real, bundle)
        and not any(part in _SKIP_DIRS for part in parts)
        and name not in _SENSITIVE
        and not name.startswith(".env.")
        and not name.endswith((".key", ".p12", ".pfx", ".pem"))
        and os.path.isfile(real)
        and not os.path.islink(path)
    )


def plan_ingest_scopes(repo_path, scope="medium", bundle_root=None):
    """Partition safe repository files into at most three deterministic, disjoint manifests."""
    if scope not in _SCOPE_WORKERS:
        raise ValueError("scope must be min, medium, or high")
    repo = os.path.realpath(repo_path)
    if not os.path.isdir(repo):
        raise ValueError("repository path is not a directory")
    bundle = os.path.realpath(bundle_root or _hook_common.bundle_root(repo))
    groups = {}
    for root, dirs, files in os.walk(repo, followlinks=False):
        dirs[:] = sorted(
            name for name in dirs
            if name not in _SKIP_DIRS
            and not os.path.islink(os.path.join(root, name))
            and not _hook_common.under(os.path.realpath(os.path.join(root, name)), bundle)
        )
        for name in sorted(files):
            path = os.path.join(root, name)
            if not _safe_file(repo, path, bundle):
                continue
            rel = os.path.relpath(path, repo).replace(os.sep, "/")
            top = rel.split("/", 1)[0] if "/" in rel else "root"
            groups.setdefault(top, []).append(rel)

    if not groups:
        return []
    worker_count = min(_SCOPE_WORKERS[scope], len(groups))
    buckets = [{"labels": [], "paths": []} for _ in range(worker_count)]
    for label, paths in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        target = min(buckets, key=lambda item: (len(item["paths"]), len(item["labels"])))
        target["labels"].append(label)
        target["paths"].extend(paths)
    total_budget = _SCOPE_CONCEPTS[scope]
    base, extra = divmod(total_budget, worker_count)
    units = []
    for index, bucket in enumerate(buckets):
        manifest = sorted(bucket["paths"])[:MAX_FILES_PER_UNIT]
        digest = hashlib.sha256("\n".join(manifest).encode("utf-8")).hexdigest()
        units.append({
            "scope_id": "ingest-%s" % digest[:12],
            "scope": ", ".join(sorted(bucket["labels"])) or "repository",
            "source_manifest": manifest,
            "source_manifest_sha256": "sha256:" + digest,
            "source_hashes": {
                path: _file_hash(os.path.join(repo, path)) for path in manifest
            },
            "concept_budget": base + (1 if index < extra else 0),
            "truncated": len(bucket["paths"]) > MAX_FILES_PER_UNIT,
        })
    return units


def dedupe_proposals(proposals, existing_entries=()):
    """Keep the first stable slug/title identity and name every dropped duplicate."""
    occupied_slugs = {
        os.path.splitext(os.path.basename(item.get("path", "")))[0].casefold()
        for item in existing_entries
    }
    occupied_titles = {str(item.get("title", "")).strip().casefold() for item in existing_entries}
    accepted, dropped = [], []
    for proposal in proposals:
        slug = str(proposal.get("slug", "")).strip().casefold()
        title = str(proposal.get("title", "")).strip().casefold()
        if not slug or not title or slug in occupied_slugs or title in occupied_titles:
            dropped.append({"slug": slug, "title": title, "reason": "duplicate-or-invalid"})
            continue
        occupied_slugs.add(slug)
        occupied_titles.add(title)
        accepted.append(proposal)
    return {"accepted": accepted, "dropped": dropped}


def main(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    selector = subparsers.add_parser("select")
    selector.add_argument("--sections-json", required=True)
    selector.add_argument("--paths-json", required=True)
    selector.add_argument("--into")
    args = parser.parse_args(argv)
    try:
        sections = json.loads(args.sections_json)
        paths = json.loads(args.paths_json)
        if not isinstance(sections, list) or not isinstance(paths, list):
            raise ValueError("sections and paths must be JSON lists")
        result = select_section(sections, paths, args.into)
    except (ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    print(json.dumps({"section": result}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
