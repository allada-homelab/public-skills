#!/usr/bin/env python3
"""PostToolUse marker-dropper — record that real code changed this turn (deterministic, silent).

When a Write/Edit touches a file that is *under the project dir* but *outside the bundle* (i.e. real
project code/docs, which often encodes a durable decision or convention), drop the
`.llm-wiki/capture-pending` marker that the **Stop** hook gates on, so the end-of-turn capture check
fires only on turns that actually changed real code, not on every turn. This hook emits nothing to
the transcript — the capture nudge is the Stop hook's job, raised once at the non-disruptive
end-of-turn moment rather than mid-turn where the model defers it. Stays silent — and writes no
marker — for bundle writes (that IS the capture), for writes *outside the project dir* (e.g. the
wiki capturer's own `/tmp` staging drafts, which would otherwise re-arm this machinery's own Stop
nudge), and when there is no bundle, so it never fires a model judgment on every tool call.

Tunable: if this proves noisy, narrow the matcher or disable the hook in hooks.json.
Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import sys

import _hook_common


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
    project = _hook_common.project_dir(event)
    if not _hook_common.bundle_exists(project):
        return 0  # no bundle — nothing to capture into
    fp_real = os.path.realpath(fp)
    if not _hook_common.under(fp_real, os.path.realpath(project)):
        return 0  # write is outside the project (e.g. capturer's /tmp draft) — not real code here
    if _hook_common.under(fp_real, os.path.realpath(_hook_common.bundle_root(project))):
        return 0  # the write IS into the bundle — not a trigger

    _mark_capture_pending(_hook_common.capture_marker(project))  # gate signal for the Stop hook: real code changed
    return 0


if __name__ == "__main__":
    sys.exit(main())
