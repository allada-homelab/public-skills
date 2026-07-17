#!/usr/bin/env python3
"""Stop hook: finalize evidence, then schedule bounded Sentinel and Scribe jobs once per change batch."""

import json
import os
import sys

import _hook_common
from catalog import load_catalog, rank_candidates
from evidence_ledger import EvidenceLedger
from impact import build_reverse_map, match_impacts
from job_state import JobController, public_job_record
from trust_boundary import delimit


def _consume(marker):
    try:
        os.remove(marker)
    except OSError:
        pass


def _marker_count(marker):
    try:
        with open(marker, encoding="utf-8") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return 1


def _prepare_impact(project, event, evidence, evidence_path, settings):
    if (
        not evidence["payload"]["changed_paths"]
        or settings["autonomy"] == "off"
        or "impact" in settings["autonomy_disabled"]
    ):
        return None
    bundle = _hook_common.bundle_root(project)
    matches = match_impacts(build_reverse_map(bundle), evidence["payload"]["changed_paths"])
    if not matches:
        return None
    controller = JobController(project, event.get("session_id"))
    job, _duplicate = controller.propose(
        feature="impact",
        origin="hook:stop",
        idempotency_key="impact:" + evidence["payload"]["revision"],
        budgets={"calls": 1, "turns": 8, "seconds": 60, "descendants": 0},
        role="worker",
    )
    if job["payload"]["state"] not in ("pending", "running"):
        return None
    request = {
        "job": public_job_record(job),
        "evidence_packet_path": evidence_path,
        "bundle_root": bundle,
        "matches": matches,
        "matched_concepts": sorted(set(item["concept"] for item in matches)),
    }
    return (
        "Dispatch `llm-wiki:wiki-sentinel` in the background. Do not wait. Surface only a returned "
        "high-confidence direct anchor as `IMPACT: <concept> — <changed path>`; shadow findings stay silent.\n"
        + delimit("impact_request", json.dumps(request, sort_keys=True, separators=(",", ":")))
    )


def _prepare_scribe(project, event, evidence, evidence_path, settings):
    changed = evidence["payload"]["changed_paths"]
    if (
        not changed
        or settings["autonomy"] == "off"
        or "scribe" in settings["autonomy_disabled"]
        or settings["capture_nudge"] == "off"
    ):
        return None
    source_hashes = {
        item["path"]: item["after_sha256"]
        for item in changed
        if isinstance(item.get("after_sha256"), str) and item["after_sha256"].startswith("sha256:")
    }
    if not source_hashes:
        return None
    controller = JobController(project, event.get("session_id"))
    job, _duplicate = controller.propose(
        feature="scribe",
        origin="hook:stop",
        idempotency_key="scribe:" + evidence["payload"]["revision"],
        budgets={"calls": 1, "turns": 12, "seconds": 120, "descendants": 0},
        role="publisher",
    )
    if job["payload"]["state"] not in ("pending", "running"):
        return None
    bundle = _hook_common.bundle_root(project)
    query = " ".join(source_hashes)
    related = [
        {key: candidate[key] for key in ("path", "title", "description", "section_path")}
        for candidate in rank_candidates(load_catalog(bundle), query, limit=8)
    ]
    request = {
        "job": public_job_record(job),
        "evidence_packet_id": evidence["packet_id"],
        "evidence_packet_path": evidence_path,
        "project": os.path.realpath(project),
        "bundle_root": bundle,
        "related_candidates": related,
        "expected_head": evidence["payload"]["current_head"],
        "source_hashes": source_hashes,
    }
    return (
        "Dispatch `llm-wiki:wiki-capturer` (Wiki Scribe) in the background. Add only a terse task "
        "summary and observed outcome from this turn to the code-owned request; do not draft the concept "
        "yourself and do not wait. Later surface exactly one breadcrumb: `wiki +1`, `wiki ~`, "
        "`wiki skipped`, `wiki stale-result`, or `wiki blocked`.\n"
        + delimit("scribe_request", json.dumps(request, sort_keys=True, separators=(",", ":")))
    )


def main():
    event = _hook_common.read_event()
    if event is None or event.get("stop_hook_active"):
        return 0
    project = _hook_common.project_dir(event)
    if not _hook_common.bundle_exists(project):
        return 0

    evidence, evidence_path = EvidenceLedger(project, event.get("session_id")).finalize()
    marker = _hook_common.capture_marker(project, event.get("session_id"))
    if not os.path.exists(marker):
        return 0
    settings = _hook_common.load_settings(project)
    impact = _prepare_impact(project, event, evidence, evidence_path, settings)
    scribe = _prepare_scribe(project, event, evidence, evidence_path, settings)
    requests = [value for value in (impact, scribe) if value is not None]
    if not requests:
        if _marker_count(marker) < settings["capture_min_edits"]:
            return 0
        _consume(marker)
        return 0

    _consume(marker)
    reason = (
        "[llm-wiki] End-of-turn coprocessors are ready. Dispatch all prepared jobs in one parallel "
        "batch; each is fire-and-forget and controller-bounded. If a request is absent, do not invent it.\n\n"
        + "\n\n".join(requests)
    )
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
