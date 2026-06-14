#!/usr/bin/env python3
"""UserPromptSubmit hook — the during-work auto-capture trigger.

Fires once per human turn. If a bundle exists, inject a terse, mode-aware nudge so the
model captures durable findings as work happens (proactive) or proposes them (curated),
rather than only when explicitly asked. The hook cannot write the concept itself — it
nudges; the model captures, and the PreToolUse secret/Doctor guards gate the write.

Deliberately terse (one line) — it fires every turn, so it must not bloat context. Emits
nothing when there is no bundle. Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import sys

from mode import resolve_mode

NUDGE = {
    "proactive": "[llm-wiki: proactive] If this turn established a durable, reusable finding "
                 "(decision, gotcha, convention, how something works), capture it to the wiki now "
                 "without waiting to be asked — it's secret-scanned, Doctor-gated, and logged. "
                 "Skip ephemeral chatter.",
    "curated": "[llm-wiki: curated] If this turn established a durable finding, propose capturing it "
               "(show the concept) but do not write without confirmation.",
    "max": "[llm-wiki: max] If this turn established a durable finding, capture it to the wiki now "
           "without waiting to be asked (secret-scanned, Doctor-gated, logged). Skip ephemera.",
}


def _project_dir(event):
    return os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    project = _project_dir(event)
    if not os.path.isfile(os.path.join(project, "llm-wiki", "index.md")):
        return 0  # no bundle here — contribute nothing
    nudge = NUDGE.get(resolve_mode(project))
    if not nudge:
        return 0
    json.dump({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": nudge,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
