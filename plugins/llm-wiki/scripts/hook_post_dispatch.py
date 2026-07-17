#!/usr/bin/env python3
"""Complete controller jobs and turn validated recall gaps into bounded background research."""

import hashlib
import json
import os
import sys

import _hook_common
from catalog import load_catalog, rank_candidates
from dispatch import select_job
from evidence_ledger import EvidenceLedger
from gap import (
    current_head,
    extract_packet,
    proposal_key,
    publication_policy,
    source_manifest,
    store_result,
)
from job_state import JobController, public_job_record
from trust_boundary import delimit


_GAP_BUDGET = {"calls": 1, "turns": 24, "seconds": 240, "descendants": 1}
_SCRIBE_BUDGET = {"calls": 1, "turns": 12, "seconds": 120, "descendants": 0}


def _failed_response(response):
    return (
        isinstance(response, dict)
        and response.get("status") in ("failed", "error", "cancelled")
    )


def _gap_requests(project, event, controller, parent, capsule):
    payload = capsule["payload"]
    if payload.get("status") != "insufficient_evidence":
        return []
    revision = current_head(project)
    baseline = EvidenceLedger(project, event.get("session_id")).initialize()
    manifest = source_manifest(project, payload.get("relevant_paths", ()))
    if not manifest:
        return []
    requests = []
    for proposal in payload.get("gap_proposals", ())[:1]:
        key = proposal_key(proposal["question"], proposal["task_scope"], revision)
        job, duplicate = controller.propose(
            feature="gap",
            origin="plugin:recall",
            idempotency_key=key,
            budgets=_GAP_BUDGET,
            role="worker",
            parent_id=parent["packet_id"],
            allow_descendants=True,
            allowed_features=("scribe",),
        )
        if duplicate or job["payload"]["state"] != "pending":
            continue
        manifest_hash = "sha256:" + hashlib.sha256("\n".join(manifest).encode("utf-8")).hexdigest()
        controller.authorize(
            job["packet_id"],
            [os.path.join(project, path) for path in manifest],
            question=proposal["question"],
            task_scope=proposal["task_scope"],
            revision=revision,
            source_manifest_sha256=manifest_hash,
        )
        job = controller.get(job["packet_id"])
        requests.append({
            "job": public_job_record(job),
            "question": proposal["question"],
            "task_scope": proposal["task_scope"],
            "wiki_gap_reason": proposal["reason"],
            "candidate_paths": proposal["candidate_paths"],
            "source_manifest": manifest,
            "source_manifest_sha256": manifest_hash,
            "repository_context": {
                "repository": baseline["repository"],
                "worktree": baseline["worktree"],
                "branch": baseline["branch"],
                "base_head": baseline["base_head"],
                "session_id": baseline["session_id"],
            },
            "revision": revision,
        })
    return requests


def _scribe_request(project, event, controller, parent, research, result_path, decision):
    payload = research["payload"]
    fingerprint = hashlib.sha256(
        json.dumps(payload["candidate"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    job, duplicate = controller.propose(
        feature="scribe",
        origin="plugin:gap",
        idempotency_key="scribe:gap:%s:%s" % (parent["packet_id"], fingerprint),
        budgets=_SCRIBE_BUDGET,
        role="publisher",
        parent_id=parent["packet_id"],
    )
    if duplicate or job["payload"]["state"] != "pending":
        return None
    bundle = _hook_common.bundle_root(project)
    related = [
        {key: candidate[key] for key in ("path", "title", "description", "section_path")}
        for candidate in rank_candidates(
            load_catalog(bundle), payload["question"] + " " + payload["candidate"]["title"], limit=8
        )
    ]
    return {
        "job": public_job_record(job),
        "purpose": "gap_research",
        "publication_allowed": True,
        "evidence_packet_id": research["packet_id"],
        "evidence_packet_path": result_path,
        "project": os.path.realpath(project),
        "bundle_root": bundle,
        "related_candidates": related,
        "expected_head": payload["revision"],
        "source_hashes": decision["source_hashes"],
    }


def _emit_gap_dispatch(requests):
    context = (
        "[llm-wiki] The forked compiler found bounded evidence gaps. Dispatch every prepared "
        "`llm-wiki:wiki-researcher` in one background batch and do not wait. These are research "
        "proposals, not answers; do not broaden their exact source manifests.\n\n"
        + delimit("gap_research_requests", json.dumps(requests, sort_keys=True, separators=(",", ":")))
    )
    _hook_common.emit_additional_context("PostToolUse", context)


def _emit_scribe_dispatch(request):
    context = (
        "[llm-wiki] Gap research passed the conservative objective-evidence gate. Dispatch "
        "`llm-wiki:wiki-capturer` in the background with this exact request and do not wait; "
        "the Scribe may still dedupe or skip.\n\n"
        + delimit("gap_scribe_request", json.dumps(request, sort_keys=True, separators=(",", ":")))
    )
    _hook_common.emit_additional_context("PostToolUse", context)


def main():
    event = _hook_common.read_event()
    if event is None or event.get("tool_name") not in ("Agent", "Skill"):
        return 0
    project = _hook_common.project_dir(event)
    controller = JobController(project, event.get("session_id"))
    job = select_job(controller, event)
    if job is None or job["payload"]["state"] != "running":
        return 0
    response = event.get("tool_response")
    if _failed_response(response):
        controller.attempt_failed(
            job["packet_id"], response.get("error") or response.get("status")
        )
        return 0

    feature = job["payload"]["feature"]
    if feature == "recall":
        capsule = extract_packet(response, "context_capsule")
        if capsule is None or capsule.get("run_id") != controller.run_id:
            controller.attempt_failed(job["packet_id"], "missing or cross-run context capsule")
            return 0
        requests = _gap_requests(project, event, controller, job, capsule)
        controller.accept_result(job["packet_id"], "context_capsule")
        if requests:
            _emit_gap_dispatch(requests)
        return 0

    if feature == "gap":
        research = extract_packet(response, "evidence_packet")
        authorization = job["payload"].get("authorization", {})
        research_payload = research.get("payload", {}) if research else {}
        if (
            research is None
            or research.get("run_id") != controller.run_id
            or research_payload.get("purpose") != "gap_research"
            or research_payload.get("job_id") != job["packet_id"]
            or research_payload.get("question") != authorization.get("question")
            or research_payload.get("task_scope") != authorization.get("task_scope")
            or research_payload.get("revision") != authorization.get("revision")
            or research_payload.get("source_manifest_sha256") != authorization.get("source_manifest_sha256")
        ):
            controller.attempt_failed(job["packet_id"], "missing or cross-run gap evidence")
            return 0
        allowed_sources = [
            os.path.relpath(path, os.path.realpath(project)).replace(os.sep, "/")
            for path in authorization.get("read_paths", ())
        ]
        decision = publication_policy(project, research, allowed_sources)
        result_path = store_result(
            project, event.get("session_id"), job["packet_id"], research, decision
        )
        request = None
        if decision["allowed"]:
            request = _scribe_request(
                project, event, controller, job, research, result_path, decision
            )
        controller.accept_result(job["packet_id"], "evidence_packet")
        if request is not None:
            _emit_scribe_dispatch(request)
        return 0

    if feature == "ingest_worker":
        evidence = extract_packet(response, "evidence_packet")
        authorization = job["payload"].get("authorization", {})
        payload = evidence.get("payload", {}) if evidence else {}
        valid = (
            evidence is not None
            and evidence.get("run_id") == controller.run_id
            and payload.get("purpose") == "ingest_proposal"
            and payload.get("job_id") == job["packet_id"]
            and payload.get("scope_id") == authorization.get("scope_id")
            and payload.get("source_manifest_sha256") == authorization.get("source_manifest_sha256")
        )
        allowed = set(authorization.get("read_paths", ()))
        repo = authorization.get("repo_root")
        for concept in payload.get("concepts", ()) if valid else ():
            for source in concept.get("sources", ()):
                if os.path.realpath(os.path.join(repo, source)) not in allowed:
                    valid = False
        if not valid:
            controller.attempt_failed(job["packet_id"], "invalid or out-of-scope ingest evidence")
            return 0
        controller.accept_result(job["packet_id"], "evidence_packet")
        return 0

    expected = {
        "parallel": "evidence_packet",
        "impact": "evidence_packet",
        "scribe": "publication_request",
    }.get(feature)
    if expected is not None:
        controller.accept_result(job["packet_id"], expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
