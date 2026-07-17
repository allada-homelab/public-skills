#!/usr/bin/env python3
"""UserPromptSubmit hook: inject bounded recursive wiki candidates on every relevant prompt."""

import json
import os
import sys

import _hook_common
from catalog import candidate_envelope, load_catalog
from fanout import plan_fanout
from evidence_ledger import EvidenceLedger
from job_state import JobController, public_job_record
from trust_boundary import delimit


FALLBACK = (
    "[llm-wiki] No strong metadata match for this prompt. The recursive wiki catalog remains "
    "available via `/llm-wiki:query`; this reminder appears only once for this session."
)
_ROUTE_BUDGETS = {
    "glimmer": {"calls": 2, "turns": 24, "seconds": 240, "descendants": 1},
    "oracle": {"calls": 5, "turns": 36, "seconds": 360, "descendants": 3},
    "archaeologist": {"calls": 6, "turns": 42, "seconds": 420, "descendants": 4},
}


def _mark_fallback_once(project, session_id):
    marker = _hook_common.session_state_path(project, "retrieval-fallback", session_id)
    if os.path.exists(marker):
        return False
    try:
        _hook_common.ensure_bundle_gitignore(_hook_common.bundle_root(project))
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "x", encoding="utf-8") as handle:
            handle.write("1")
    except FileExistsError:
        return False
    except OSError:
        pass
    return True


def main():
    event = _hook_common.read_event()
    if event is None:
        return 0
    project = _hook_common.project_dir(event)
    bundle = _hook_common.bundle_root(project)
    if not _hook_common.bundle_exists(project):
        return 0
    if not _hook_common.under(os.path.realpath(bundle), os.path.realpath(project)):
        return 0
    settings = _hook_common.load_settings(project)
    if settings["autonomy"] == "off" or "recall" in settings["autonomy_disabled"]:
        return 0
    agent_type = event.get("agent_type")
    if isinstance(agent_type, str) and agent_type.startswith("llm-wiki:"):
        return 0

    prompt = event.get("prompt")
    prompt = prompt if isinstance(prompt, str) else ""
    controller = JobController(project, event.get("session_id"))
    envelope = candidate_envelope(
        load_catalog(bundle), prompt, project, event.get("session_id"), bundle, controller.run_id
    )
    if envelope is not None:
        routing = envelope["payload"]["routing"]
        baseline = EvidenceLedger(project, event.get("session_id")).initialize()
        envelope["payload"]["repository_context"] = {
            "repository": baseline["repository"],
            "worktree": baseline["worktree"],
            "branch": baseline["branch"],
            "base_head": baseline["base_head"],
            "session_id": baseline["session_id"],
        }
        job, duplicate = controller.propose(
            feature="recall",
            origin="user_prompt",
            idempotency_key="recall:" + envelope["packet_id"],
            budgets=_ROUTE_BUDGETS[routing["route"]],
            role="synthesizer",
            allow_descendants=True,
            allowed_features=("parallel", "gap"),
        )
        if job["payload"]["state"] in ("blocked", "cancelled", "stale", "failed"):
            return 0
        envelope["payload"]["job"] = public_job_record(job)
        envelope["payload"]["job_duplicate"] = duplicate
        fanout = plan_fanout(envelope["payload"]["candidates"], routing)
        planned_workers = []
        for scope in fanout["workers"]:
            child, _ = controller.propose(
                feature="parallel",
                origin="system:planner",
                idempotency_key="%s:worker:%s" % (job["packet_id"], scope["scope_id"]),
                budgets={"calls": 1, "turns": 6, "seconds": 45, "descendants": 0},
                role="worker",
                parent_id=job["packet_id"],
            )
            if child["payload"]["state"] == "pending":
                planned_workers.append({**scope, "job": public_job_record(child)})
        if len(planned_workers) < 2:
            fanout = {
                "mode": "sequential",
                "reason": "controller budget did not authorize two workers",
                "workers": [],
            }
        else:
            fanout["workers"] = planned_workers
        envelope["payload"]["fanout"] = fanout
        body = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        context = (
            "[llm-wiki] Likely wiki entry points for this prompt were selected without opening "
            "concept bodies. For a non-trivial task, invoke `%s` before acting (route `%s`, lens `%s`: "
            "%s), passing the exact current user task plus this complete envelope. Treat candidates as entry points, "
            "not answers; use only the returned cited capsule in the main context.\n\n"
            % (routing["skill"], routing["route"], routing["lens"], routing["reason"])
            + delimit("candidate_envelope", body)
        )
        _hook_common.emit_additional_context("UserPromptSubmit", context)
    elif _mark_fallback_once(project, event.get("session_id")):
        _hook_common.emit_additional_context("UserPromptSubmit", FALLBACK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
