#!/usr/bin/env python3
"""PostToolUse pre-filter — a cheap, mostly-silent capture nudge after real-code edits.

A secondary trigger to the UserPromptSubmit nudge: when a Write/Edit/MultiEdit touches a
file *outside* the bundle (i.e. real project code/docs, which often encodes a durable
decision or convention) and the wiki is in an auto mode, drop a terse reminder to capture
it. Stays silent for bundle writes (that IS the capture), for curated mode, and when there
is no bundle — so it never fires a model judgment on every tool call.

Tunable: if this proves noisy, narrow the matcher or disable the hook in hooks.json.
Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import sys

from mode import resolve_mode


def _under(path_abs, root_abs):
    try:
        return os.path.commonpath([root_abs, path_abs]) == root_abs
    except ValueError:
        return False


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    fp = (event.get("tool_input") or {}).get("file_path")
    if not fp:
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    if not os.path.isfile(os.path.join(project, "llm-wiki", "index.md")):
        return 0  # no bundle — nothing to capture into
    if _under(os.path.realpath(fp), os.path.realpath(os.path.join(project, "llm-wiki"))):
        return 0  # the write IS into the bundle — not a trigger
    if resolve_mode(project) not in ("proactive", "max"):
        return 0  # only auto-nudge in an auto mode

    nudge = ("[llm-wiki] You just changed %s — if that established a durable decision, convention, "
             "or gotcha, capture it to the wiki now (it's secret-scanned, Doctor-gated, logged)."
             % os.path.basename(fp))
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": nudge,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
