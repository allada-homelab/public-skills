#!/usr/bin/env python3
"""UserPromptSubmit hook — the start-of-session "consult the wiki" nudge.

The read loop is the wiki's whole value ("start smarter"), yet it was the only half with no
forcing function — capture had several (SessionStart instruction, PostToolUse, the Stop hook),
consult had none, so it didn't happen. This hook fixes that asymmetry: once per session, on the
first prompt, if a bundle exists, inject a terse nudge to consult the wiki before non-trivial
work and state what was found.

Deliberately fires *once per session*, not every turn: a signal that fires every turn carries no
information about which turn warrants action (and trains the model to tune it out). Capture is
handled end-of-turn by the Stop hook, so this hook no longer carries a per-turn capture nudge.
Session identity is the event `session_id`; the last-seen value is recorded in the
`.llm-wiki/last-session` marker so the nudge fires exactly once per session (falling back to
once-per-bundle when no `session_id` is provided). Silent when there is no bundle. Reads
`$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import sys

CONSULT = (
    "[llm-wiki] New session — the wiki is preloaded above. Before a non-trivial task, consult it "
    "first: `/llm-wiki:query <question>` or `/llm-wiki:explore`, and state what you found (or that "
    "nothing was relevant). Treat it as a first-class source alongside CLAUDE.md and READMEs — the "
    "wiki holds consulted, reusable knowledge (findings, decisions, runbooks, schemas); in-tree docs "
    "hold always-on, file-local specifics. Capture durable findings to it as you work."
)


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
    marker = os.path.join(project, "llm-wiki", ".llm-wiki", "last-session")
    token = str(event.get("session_id") or "__nosession__")
    try:
        prev = open(marker, encoding="utf-8").read().strip()
    except OSError:
        prev = None
    if prev == token:
        return 0  # already nudged this session — stay silent (capture is the Stop hook's job)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(token)
    except OSError:
        pass  # best-effort: a failed marker write just means the nudge may repeat

    json.dump({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": CONSULT,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
