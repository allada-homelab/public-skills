"""Deterministic planner for bounded, disjoint recall-worker fan-out."""

import hashlib


def plan_fanout(candidates, routing):
    route = routing.get("route")
    if route == "glimmer":
        return {"mode": "sequential", "reason": "Glimmer never fans out", "workers": []}
    by_section = {}
    for candidate in candidates:
        section = candidate.get("section_path") or "root"
        by_section.setdefault(section, []).append(candidate["path"])
    if len(by_section) < 2:
        return {
            "mode": "sequential",
            "reason": "candidate evidence is concentrated in one section",
            "workers": [],
        }
    limit = 2 if route == "oracle" else 3
    workers = []
    for section, paths in sorted(by_section.items())[:limit]:
        scope_key = section + "\0" + "\0".join(sorted(paths))
        workers.append({
            "scope_id": hashlib.sha256(scope_key.encode("utf-8")).hexdigest()[:12],
            "section": section,
            "candidate_paths": sorted(paths),
            "turn_budget": 6,
        })
    return {
        "mode": "parallel",
        "reason": "%d independent top-level sections" % len(workers),
        "workers": workers,
    }
