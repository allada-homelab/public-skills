#!/usr/bin/env python3
"""SessionStart hook — preload the llm-wiki into context (deterministic, no model call).

If a bundle exists at `$CLAUDE_PROJECT_DIR/llm-wiki/`, inject its root `index.md` plus a
one-line active-mode notice via the SessionStart `additionalContext` channel, so each
session starts knowing the wiki's shape and whether it is in auto (proactive) mode. If no
bundle exists, emit nothing and exit 0 — never block or noise a session that has no wiki.

Reads `$CLAUDE_PROJECT_DIR` (falls back to the event JSON's `cwd`, else cwd).
"""
import json
import os
import sys

from mode import resolve_mode

MODE_NOTE = {
    "proactive": "auto — findings are captured and indexes/log maintained without per-write "
                 "confirmation (every write is secret-scanned, Doctor-gated, logged, and git-reversible). "
                 "Switch with `mode: curated` in .claude/llm-wiki.local.md.",
    "curated": "propose-only — captures are proposed, never written without your confirmation.",
    "max": "auto + background curation (proactive plus the deferred Max tail).",
}


def _project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return env
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if isinstance(event, dict) and event.get("cwd"):
            return event["cwd"]
    except (ValueError, OSError):
        pass
    return os.getcwd()


def main():
    project_dir = _project_dir()
    index_path = os.path.join(project_dir, "llm-wiki", "index.md")
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            index = fh.read()
    except OSError:
        return 0  # no bundle here — contribute nothing

    mode = resolve_mode(project_dir)
    context = (
        "# llm-wiki knowledge bundle (preloaded)\n\n"
        "Active mode: **%s** — %s\n\n"
        "Root index (`llm-wiki/index.md`) — explore/query for details, capture findings as you work:\n\n"
        "%s" % (mode, MODE_NOTE.get(mode, ""), index)
    )
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
