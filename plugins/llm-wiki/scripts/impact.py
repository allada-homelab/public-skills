"""Deterministic changed-path -> wiki concept reverse map for the impact radar."""

import os
import re

import _hook_common
from doctor import OK, parse_frontmatter


MAX_CONCEPTS = 4096
MAX_BYTES = 2 * 1024 * 1024
_LINK = re.compile(r"\[[^\]]+\]\(([^)#?]+)")
_BACKTICK_PATH = re.compile(r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)`")


def _concept_files(bundle):
    out = []
    for current, dirs, files in os.walk(bundle, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name != ".llm-wiki")
        for name in sorted(files):
            if not name.endswith(".md") or name in ("index.md", "log.md"):
                continue
            out.append(os.path.join(current, name))
            if len(out) >= MAX_CONCEPTS:
                return out
    return out


def _verify_paths(text):
    paths, in_verify = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            in_verify = line[3:].strip().lower() == "verify"
            continue
        if not in_verify or not line.lstrip().startswith(("- ", "* ")):
            continue
        token = line.lstrip()[2:].split()[0] if line.lstrip()[2:].split() else ""
        if not token or token.lower().startswith("run:"):
            continue
        path = token.split(":", 1)[0]
        if "/" in path or "." in path:
            paths.append(path.replace("\\", "/"))
    return paths


def build_reverse_map(bundle_root):
    bundle = os.path.realpath(bundle_root)
    concepts, links, total = {}, {}, 0
    for path in _concept_files(bundle):
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        total += len(text.encode("utf-8"))
        if total > MAX_BYTES:
            break
        relpath = os.path.relpath(path, bundle).replace(os.sep, "/")
        status, fm = parse_frontmatter(text)
        resources = []
        if status == OK and isinstance(fm, dict):
            raw = fm.get("resource", [])
            resources = raw if isinstance(raw, list) else ([raw] if isinstance(raw, str) and raw else [])
        references = list(_BACKTICK_PATH.findall(text))
        concepts[relpath] = {
            "verify": sorted(set(_verify_paths(text))),
            "resource": sorted(set(str(value).split(":", 1)[0] for value in resources)),
            "reference": sorted(set(references)),
            "section": relpath.split("/", 1)[0] if "/" in relpath else "root",
        }
        targets = []
        for raw in _LINK.findall(text):
            target = os.path.realpath(os.path.join(os.path.dirname(path), raw))
            if _hook_common.under(target, bundle) and target.endswith(".md"):
                targets.append(os.path.relpath(target, bundle).replace(os.sep, "/"))
        links[relpath] = sorted(set(targets))
    return {"concepts": concepts, "links": links}


def match_impacts(reverse_map, changed_paths, max_depth=3):
    changed = sorted(set(
        item["path"] if isinstance(item, dict) else str(item)
        for item in changed_paths
    ))
    findings = []
    direct_concepts = set()
    direct_chains = {}
    for concept, metadata in reverse_map["concepts"].items():
        for edge_kind, confidence in (("verify", 1.0), ("resource", 0.9), ("reference", 0.7)):
            for source in metadata[edge_kind]:
                for changed_path in changed:
                    if changed_path == source or changed_path.startswith(source.rstrip("/") + "/"):
                        findings.append({
                            "concept": concept,
                            "edge_kind": edge_kind,
                            "changed_path": changed_path,
                            "source_path": source,
                            "chain": [changed_path, concept],
                            "confidence": confidence,
                            "surface": edge_kind in ("verify", "resource"),
                        })
                        direct_concepts.add(concept)
                        direct_chains.setdefault(concept, [changed_path, concept])
    reverse_links = {}
    for source, targets in reverse_map["links"].items():
        for target in targets:
            reverse_links.setdefault(target, []).append(source)
    frontier = [(concept, direct_chains[concept], 0) for concept in sorted(direct_concepts)]
    seen = set(direct_concepts)
    while frontier:
        target, chain, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for dependent in sorted(reverse_links.get(target, [])):
            if dependent in seen:
                continue
            seen.add(dependent)
            next_chain = chain + [dependent]
            findings.append({
                "concept": dependent,
                "edge_kind": "concept_link",
                "changed_path": "",
                "source_path": target,
                "chain": next_chain,
                "confidence": round(0.8 - 0.15 * depth, 2),
                "surface": False,
            })
            frontier.append((dependent, next_chain, depth + 1))
    findings.sort(key=lambda item: (-item["confidence"], item["concept"], item["edge_kind"]))
    return findings
