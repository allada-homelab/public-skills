#!/usr/bin/env python3
"""Preflight, dedupe, place, and provenance-stamp one bounded ingest proposal batch."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

from catalog import load_catalog
from gap import current_head
from packet_contracts import SCHEMA, VERSION, validate_packet
from provenance import file_fingerprint
from publication import prepare
from topology import dedupe_proposals, select_section, validate_section


_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def _absolute_hash(path):
    if not os.path.isfile(path):
        return None
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("ingest batch must be a JSON object")
    return value


def _content(proposal):
    if not _TYPE.fullmatch(str(proposal.get("type", ""))):
        raise ValueError("concept type must be a compact token")
    title, description = proposal.get("title"), proposal.get("description")
    body = proposal.get("body_markdown")
    if not all(isinstance(value, str) and value.strip() for value in (title, description, body)):
        raise ValueError("concept title, description, and body_markdown are required")
    return (
        "---\n"
        "type: %s\n"
        "title: %s\n"
        "description: %s\n"
        "---\n\n%s\n"
        % (
            proposal["type"],
            json.dumps(title.strip(), ensure_ascii=False),
            json.dumps(description.strip(), ensure_ascii=False),
            body.strip(),
        )
    )


def prepare_batch(value, output_path):
    project = os.path.realpath(value.get("project", ""))
    bundle = os.path.realpath(value.get("bundle_root", ""))
    expected_head = value.get("expected_head")
    if not os.path.isdir(project) or current_head(project) != expected_head:
        return {"status": "stale-result", "reason": "repository HEAD changed"}
    source_manifest = value.get("source_manifest")
    if not isinstance(source_manifest, list) or not source_manifest:
        raise ValueError("source_manifest must be a non-empty list")
    expected_source_hashes = value.get("expected_source_hashes")
    if not isinstance(expected_source_hashes, dict):
        raise ValueError("expected_source_hashes must be a mapping from the ingest plan")
    allowed_sources = set()
    for source in source_manifest:
        current_hash = file_fingerprint(project, source) if isinstance(source, str) else None
        if not isinstance(source, str) or os.path.isabs(source) or current_hash is None:
            raise ValueError("source manifest contains an unsafe or missing path")
        if expected_source_hashes.get(source) != current_hash:
            return {"status": "stale-result", "reason": "source hash changed", "source": source}
        allowed_sources.add(source)
    proposals = value.get("concepts")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 40:
        raise ValueError("concepts must contain 1..40 proposals")
    catalog = load_catalog(bundle)
    deduped = dedupe_proposals(proposals, catalog["entries"])
    if not deduped["accepted"]:
        raise ValueError("every proposal duplicates existing or accepted knowledge")
    explicit = validate_section(value["into"]) if value.get("into") else None
    existing_sections = [row["path"] for row in catalog["sections"] if row["path"]]

    prepared, seen_paths, expected_destinations = [], set(), {}
    for proposal in deduped["accepted"]:
        slug = str(proposal.get("slug", ""))
        if not _SLUG.fullmatch(slug):
            raise ValueError("concept slug is invalid: %s" % slug)
        claims = proposal.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError("every ingest concept requires objective claims")
        sources = set()
        for claim in claims:
            claim_sources = claim.get("sources", ()) if isinstance(claim, dict) else ()
            for source in claim_sources:
                path = source.get("source") if isinstance(source, dict) else None
                if path not in allowed_sources:
                    raise ValueError("proposal cites a source outside its explorer manifests")
                sources.add(path)
        if not sources:
            raise ValueError("every ingest concept requires at least one manifest source")
        section = select_section(existing_sections, sorted(sources), explicit)
        concept_path = "%s%s.md" % ((section + "/") if section else "", slug)
        if concept_path in seen_paths:
            raise ValueError("duplicate final concept path: %s" % concept_path)
        seen_paths.add(concept_path)
        expected_destinations[concept_path] = _absolute_hash(os.path.join(bundle, concept_path))
        source_hashes = {source: file_fingerprint(project, source) for source in sorted(sources)}
        packet = {
            "schema": SCHEMA,
            "version": VERSION,
            "kind": "publication_request",
            "packet_id": "ingest-%s" % slug,
            "run_id": str(value.get("run_id") or "ingest"),
            "payload": {
                "evidence_packet_id": str(value.get("evidence_packet_id") or "ingest-evidence"),
                "project": project,
                "bundle_root": bundle,
                "concept_path": concept_path,
                "content": _content(proposal),
                "claims": claims,
                "expected_head": expected_head,
                "source_hashes": source_hashes,
                "log_kind": "Creation",
                "log_message": "Ingested [%s](./%s)." % (proposal["title"], concept_path),
                "plugin_version": str(value.get("plugin_version") or "0.1.0"),
                # Feeds both the evidence record and the §5.2 `generated.by` actor.
                "model": str(value.get("model") or "sonnet"),
            },
        }
        validate_packet(packet, "publication_request")
        fd, temp_path = tempfile.mkstemp(prefix="llm-wiki-ingest-concept-", suffix=".md")
        os.close(fd)
        try:
            result = prepare(packet, temp_path)
            if result["status"] != "prepared":
                return result
            with open(temp_path, encoding="utf-8") as handle:
                prepared.append({"path": concept_path, "content": handle.read()})
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    titles = [item["path"] for item in prepared]
    manifest = {
        "concepts": prepared,
        "project": project,
        "expected_head": expected_head,
        "expected_source_hashes": {
            source: expected_source_hashes[source] for source in sorted(allowed_sources)
        },
        "expected_destinations": expected_destinations,
        "log_message": "Ingested %d grounded concept%s: %s" % (
            len(prepared), "" if len(prepared) == 1 else "s", ", ".join(titles)
        ),
        "dropped": deduped["dropped"],
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"status": "prepared", "concepts": titles, "dropped": len(deduped["dropped"])}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: batch_publication.py <ingest-batch.json> <prepared-manifest.json>\n")
        return 2
    try:
        result = prepare_batch(_load(argv[0]), argv[1])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 3 if result["status"] == "stale-result" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
