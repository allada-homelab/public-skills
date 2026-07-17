#!/usr/bin/env python3
"""PostToolUse marker-dropper — record that real code changed this turn (deterministic, silent).

When a Write/Edit touches a file that is *under the project dir* but *outside the bundle* (i.e. real
project code/docs, which often encodes a durable decision or convention), drop the session-scoped
`.llm-wiki/capture-pending-<session_id>` marker that the **Stop** hook gates on, so the end-of-turn capture check
fires only on turns that actually changed real code, not on every turn. This hook emits nothing to
the transcript — the capture nudge is the Stop hook's job, raised once at the non-disruptive
end-of-turn moment rather than mid-turn where the model defers it. Stays silent — and writes no
marker — for bundle writes (that IS the capture), for writes *outside the project dir* (e.g. the
wiki capturer's own `/tmp` staging drafts, which would otherwise re-arm this machinery's own Stop
nudge), and when there is no bundle, so it never fires a model judgment on every tool call.

Tunable: if this proves noisy, narrow the matcher or disable the hook in hooks.json.
Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import os
import sys

import _hook_common
from evidence_ledger import EvidenceLedger


def _mark_capture_pending(marker, bundle):
    """Increment the marker's edit count, signalling 'real code changed this turn'. The marker's
    content is a decimal count of qualifying edits so the Stop hook can throttle on it: a missing
    marker starts the count at 1, and a legacy/empty/unparseable one is treated as 1 (so it
    increments to 2). Ensures the bundle `.gitignore` covers the transient `.llm-wiki/` state
    dir before writing into it. Best-effort: never break a real tool call over marker bookkeeping
    — a failed write just keeps the end-of-turn Stop nudge silent for this change."""
    try:
        _hook_common.ensure_bundle_gitignore(bundle)
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        try:
            with open(marker, encoding="utf-8") as fh:
                count = int(fh.read().strip())
        except OSError:
            count = 0  # no marker yet — this is the turn's first qualifying edit
        except ValueError:
            count = 1  # legacy/empty/unparseable marker — treat as one prior edit
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(str(count + 1))
    except OSError:
        pass


def main():
    event = _hook_common.read_event()
    if event is None:
        return 0
    agent_type = event.get("agent_type")
    if isinstance(agent_type, str) and agent_type.startswith("llm-wiki:"):
        return 0  # plugin-originated writes never arm autonomous descendants
    fp = _hook_common.event_file_path(event)
    if fp is None:
        return 0
    project = _hook_common.project_dir(event)
    if not _hook_common.bundle_exists(project):
        return 0  # no bundle — nothing to capture into
    fp_real = os.path.realpath(fp)
    if not _hook_common.under(fp_real, os.path.realpath(project)):
        return 0  # write is outside the project (e.g. capturer's /tmp draft) — not real code here
    bundle = _hook_common.bundle_root(project)
    if _hook_common.under(fp_real, os.path.realpath(bundle)):
        return 0  # the write IS into the bundle — not a trigger

    EvidenceLedger(project, event.get("session_id")).record_tool_event(event)

    # gate signal for the Stop hook: real code changed — scoped to this session's id so a
    # concurrent session/process in the same project can't arm another session's nudge
    _mark_capture_pending(_hook_common.capture_marker(project, event.get("session_id")), bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
