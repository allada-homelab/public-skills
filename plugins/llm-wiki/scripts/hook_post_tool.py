#!/usr/bin/env python3
"""PostToolUse pre-filter — a cheap, mostly-silent capture nudge after real-code edits.

A secondary trigger to the UserPromptSubmit nudge: when a Write/Edit touches a
file *outside* the bundle (i.e. real project code/docs, which often encodes a durable
decision or convention) and the wiki is in an auto mode, drop a terse reminder to capture
it, and drop the `.llm-wiki/capture-pending` marker that the **Stop** hook gates on (so the
end-of-turn capture check fires only on turns that actually changed real code, not on every
turn). The nudge is emitted only on the *first* real-code edit of a turn — gated on the marker
not yet existing — so subsequent edits in the same batch stay silent (the marker is still
ensured present); this is what keeps the hook "mostly-silent" instead of nudging every edit.
Stays silent — and writes no marker — for bundle writes (that IS the capture), for
curated mode, and when there is no bundle, so it never fires a model judgment on every tool call.

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


def _marker_path(project):
    return os.path.join(project, "llm-wiki", ".llm-wiki", "capture-pending")


def _mark_capture_pending(marker):
    """Drop the marker the Stop hook gates on, signalling 'real code changed this turn'.
    Best-effort: never break a real tool call over marker bookkeeping — if the write fails,
    the only consequence is the end-of-turn Stop nudge stays silent for this change."""
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        open(marker, "w").close()
    except OSError:
        pass


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

    marker = _marker_path(project)
    first_edit = not os.path.exists(marker)  # marker absent → first real-code edit of this turn
    _mark_capture_pending(marker)  # gate signal for the Stop hook: real code changed this turn
    if not first_edit:
        return 0  # already nudged this turn — stay silent, just keep the marker fresh

    nudge = ("[llm-wiki] You just changed %s — if that established a durable decision, convention, "
             "gotcha, or failure->fix (an approach that failed and the one that worked), capture it "
             "to the wiki now (it's secret-scanned, Doctor-gated, logged); in an auto mode apply it "
             "silently, without announcing what you saved." % os.path.basename(fp))
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": nudge,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
