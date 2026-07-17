#!/usr/bin/env python3
"""Prepare a provenance-stamped concept after a branch/HEAD/source-hash preflight."""

from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys

from packet_contracts import load_packet
from provenance import claim_id, evidence_id, file_fingerprint, render, strip


def _git_head(project):
    try:
        proc = subprocess.run(
            ["git", "-C", project, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unborn"
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unborn"


def _ensure_managed_frontmatter(content):
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("content must have frontmatter")
    try:
        close = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("content frontmatter is not closed") from exc
    if any(line.split(":", 1)[0].strip() == "wiki_managed" for line in lines[1:close]):
        lines = [
            "wiki_managed: true" if line.split(":", 1)[0].strip() == "wiki_managed" else line
            for line in lines
        ]
    else:
        lines.insert(close, "wiki_managed: true")
    return "\n".join(lines).rstrip() + "\n"


def _approved_gap_content(payload):
    path = payload.get("evidence_packet_path")
    if not isinstance(path, str):
        raise ValueError("gap publication requires evidence_packet_path")
    try:
        with open(path, encoding="utf-8") as handle:
            research = load_packet(handle.read(), "evidence_packet")
    except OSError as exc:
        raise ValueError("cannot read approved gap evidence: %s" % exc) from exc
    research_payload = research["payload"]
    if (
        research["packet_id"] != payload["evidence_packet_id"]
        or research_payload.get("purpose") != "gap_research"
        or research_payload.get("publication_allowed") is not True
    ):
        raise ValueError("gap evidence is not approved for publication")
    candidate = research_payload["candidate"]
    claims = research_payload["claims"]
    concept_type = candidate["type"]
    title = " ".join(candidate["title"].split())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", concept_type) or not title:
        raise ValueError("approved gap candidate metadata is unsafe")
    statements = "\n".join(
        "- %s" % " ".join(claim["statement"].split()) for claim in claims
    )
    return (
        "---\ntype: %s\ntitle: %s\ndescription: %s\n---\n\n# %s\n\n%s\n"
        % (
            concept_type,
            json.dumps(title, ensure_ascii=False),
            json.dumps(candidate["description"], ensure_ascii=False),
            title,
            statements,
        )
    )


def prepare(packet, output_path):
    payload = packet["payload"]
    project = os.path.realpath(payload.get("project", ""))
    if not project or not os.path.isdir(project):
        raise ValueError("payload.project must be a repository directory")
    current_head = _git_head(project)
    if current_head != payload["expected_head"]:
        return {"status": "stale-result", "reason": "repository HEAD changed"}
    for source, expected in payload["source_hashes"].items():
        if file_fingerprint(project, source) != expected:
            return {"status": "stale-result", "reason": "source hash changed", "source": source}

    claims_input = payload.get("claims")
    if not isinstance(claims_input, list) or not claims_input:
        raise ValueError("payload.claims must be a non-empty list")
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence, evidence_seen, claims = [], set(), []
    for claim in claims_input:
        statement = claim["statement"]
        scope = claim["scope"]
        refs = []
        for source in claim["sources"]:
            source_path = source["source"]
            digest = payload["source_hashes"].get(source_path)
            if digest is None:
                raise ValueError("claim source has no source hash: %s" % source_path)
            item_id = evidence_id(source_path, digest, current_head, scope)
            refs.append(item_id)
            if item_id in evidence_seen:
                continue
            evidence_seen.add(item_id)
            evidence.append({
                "id": item_id,
                "source_kind": source["source_kind"],
                "source": source_path,
                "content_sha256": digest,
                "repository_head": current_head,
                "scope": scope,
                "producer": "wiki-scribe",
                "model": "sonnet",
                "plugin_version": payload.get("plugin_version", "0.1.0"),
                "captured_at": captured_at,
                "derived_from": [],
            })
        claims.append({
            "id": claim_id(statement, scope),
            "statement": statement,
            "classification": claim["classification"],
            "scope": scope,
            "evidence_ids": refs,
        })
    document = {"version": 1, "claims": claims, "evidence": evidence}
    source_content = (
        _approved_gap_content(payload)
        if payload.get("purpose") == "gap_research"
        else payload["content"]
    )
    content = _ensure_managed_frontmatter(strip(source_content))
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n\n" + render(document) + "\n")
    return {"status": "prepared", "claims": len(claims), "evidence": len(evidence)}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: publication.py <publication-request.json> <output.md>\n")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as handle:
            packet = load_packet(handle.read(), "publication_request")
        result = prepare(packet, argv[1])
    except (OSError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 3 if result["status"] == "stale-result" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
