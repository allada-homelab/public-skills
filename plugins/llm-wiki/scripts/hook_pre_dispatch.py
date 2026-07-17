#!/usr/bin/env python3
"""PreToolUse gate that starts only controller-issued llm-wiki recall/worker dispatches."""

import json
import sys

import _hook_common
from dispatch import select_job, target_name
from job_state import JobController


_PROTECTED_AGENTS = frozenset({
    "wiki-glimmer", "wiki-compiler", "wiki-archaeologist", "wiki-evidence-worker", "wiki-sentinel",
    "wiki-capturer", "wiki-researcher", "wiki-explorer",
})
_PROTECTED_SKILLS = frozenset({"recall-glimmer", "recall", "recall-archaeologist"})


def _deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def main():
    event = _hook_common.read_event()
    if event is None:
        return 0
    target = target_name(event)
    protected = (
        event.get("tool_name") == "Agent" and target in _PROTECTED_AGENTS
    ) or (
        event.get("tool_name") == "Skill" and target in _PROTECTED_SKILLS
    )
    if not protected:
        return 0

    controller = JobController(_hook_common.project_dir(event), event.get("session_id"))
    packet = select_job(controller, event)
    if packet is None:
        _deny("llm-wiki controller requires one target-matching issued job for this dispatch.")
        return 0
    state = packet["payload"]["state"]
    if state == "pending" and controller.start(packet["packet_id"]):
        return 0
    if (
        state == "running"
        and event.get("tool_name") == "Agent"
        and target in ("wiki-glimmer", "wiki-compiler", "wiki-archaeologist")
        and packet["payload"]["feature"] == "recall"
    ):
        return 0  # the enclosing forked Skill started this one internal route resolution
    _deny("llm-wiki controller rejected a job that is not startable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
