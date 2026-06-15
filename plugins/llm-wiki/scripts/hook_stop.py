#!/usr/bin/env python3
"""Stop hook — the end-of-turn capture forcing function (reliable auto-capture trigger).

The UserPromptSubmit / PostToolUse nudges fire *mid-turn*, where the model tends to defer
capture in favour of the in-flight task, so durable findings slip by uncaptured. This hook
fires when the turn is *finishing* — the non-disruptive moment to capture — and, in an auto
mode, blocks the stop once to make the model actually decide: capture a durable finding now,
or explicitly stop.

Mechanism (Claude Code Stop-hook contract): emit
`{"decision": "block", "reason": ..., "hookSpecificOutput": {... "additionalContext": ...}}`
at exit 0 to continue the turn with the instruction injected; emit nothing to allow the stop.
`stop_hook_active` is true on the re-fire *after* a block, so we exit 0 then — the model is
nudged at most once per turn (the loop guard). Silent for curated mode and when no bundle
exists. Reads `$CLAUDE_PROJECT_DIR` (falls back to the event JSON's `cwd`).

The model is the judge: a deterministic hook cannot know whether a durable finding occurred,
so the reason text gives a clean "nothing durable → just stop" out. Loop prevention leans on
`stop_hook_active` (Claude Code issue #54360 tracked a past propagation bug); the worst case
if that regresses is a repeated end-of-turn nudge — never an unsafe or non-conformant write,
since every capture still passes the PreToolUse secret/Doctor guard floor.
"""
import json
import os
import sys

from mode import resolve_mode

NUDGE = (
    "[llm-wiki] Before finishing this turn: if it established a durable, reusable finding "
    "(a decision, gotcha, convention, schema, or how something works), capture it to the wiki "
    "now via /llm-wiki:capture — it is secret-scanned, Doctor-gated, logged, and git-reversible. "
    "If nothing durable happened this turn, just stop without capturing — do not invent a finding."
)


def _project_dir(event):
    return os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    if event.get("stop_hook_active"):
        return 0  # already nudged once this turn — allow the stop (loop guard)
    project = _project_dir(event)
    if not os.path.isfile(os.path.join(project, "llm-wiki", "index.md")):
        return 0  # no bundle here — contribute nothing
    if resolve_mode(project) not in ("proactive", "max"):
        return 0  # only force the end-of-turn check in an auto mode

    json.dump({
        "decision": "block",
        "reason": NUDGE,
        "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": NUDGE},
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
