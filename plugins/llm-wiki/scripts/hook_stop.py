#!/usr/bin/env python3
"""Stop hook — the end-of-turn capture forcing function (reliable auto-capture trigger).

The UserPromptSubmit / PostToolUse nudges fire *mid-turn*, where the model tends to defer
capture in favour of the in-flight task, so durable findings slip by uncaptured. This hook
fires when the turn is *finishing* — the non-disruptive moment to capture — and blocks the stop
once to make the model actually decide: draft a durable finding and dispatch the background
`wiki-capturer` subagent to persist it (plus `wiki-verifier` for any anchor it touched), or
explicitly stop. The mechanical write lives in the subagents; the main loop never blocks on them.

Mechanism (Claude Code Stop-hook contract): emit `{"decision": "block", "reason": ...}` at exit
0 to continue the turn with the reason injected; emit nothing to allow the stop. (The doc names
`decision: "block"` + `reason` as the canonical Stop blocking channel, so we emit only that — no
redundant `hookSpecificOutput.additionalContext` carrying the same text.) Gated by the
`.llm-wiki/capture-pending` marker that the PostToolUse hook drops on a real-code edit: with no
marker (a pure-chat turn that changed nothing) this hook stays silent, so it does not force a
continuation on every turn. Also silent when no bundle exists. Reads `$CLAUDE_PROJECT_DIR`
(falls back to the event JSON's `cwd`).

The model is the judge: a deterministic hook cannot know whether a durable finding occurred,
so the reason text gives a clean "nothing durable → just stop" out.

Loop guard: the load-bearing guard is *marker consumption* — this hook removes the
`capture-pending` marker before emitting `block`, so the forced re-fire finds no marker and
allows the stop (one nudge per change-batch, regardless of whether `stop_hook_active` is
delivered). `stop_hook_active` is a secondary fast-path: when present and true on the re-fire we
exit 0 immediately, but it may not always be delivered (Claude Code issue #54360 tracked a past
propagation bug), which is exactly why the marker — not `stop_hook_active` — is what makes the
guard robust. The worst case if both regressed is a repeated end-of-turn nudge — never an unsafe
or non-conformant write, since every capture still passes the PreToolUse secret/Doctor guard floor.
"""
import json
import os
import sys

import _hook_common

NUDGE = (
    "[llm-wiki] Before finishing this turn, run the wiki's end-of-turn loop (fire-and-forget — do not "
    "block on the subagents): "
    "(1) If this turn established a durable, reusable finding (a decision; a gotcha — e.g. a silent "
    "footgun, a surprising root cause, or a failure->fix where one approach failed and another worked; "
    "a convention, schema, or how something works), DRAFT it now per the wiki skill and dispatch the "
    "`wiki-capturer` subagent in the BACKGROUND to persist it through the gated apply engine. The "
    "capturer inherits nothing from this conversation, so hand it everything it needs: the "
    "bundle-relative concept path, the full drafted body (frontmatter included), the log kind "
    "(`Creation` for a new concept, `Update` for an edit) and a linked log message, and the bundle "
    "root. Do not write the concept to the bundle inline. After dispatching the capturer, do not "
    "summarize the concept — at most one breadcrumb line in your next user-visible message: "
    "`wiki +1: <title>` for a new concept, `wiki ~: <title>` for an update. If the capturer reports a "
    "blocked apply, ALWAYS surface it as `wiki blocked (<doctor|secret>): <path>` — a silently-blocked "
    "capture is the failure mode this exists to prevent. "
    "(2) Find wiki concepts that verify a file you touched: grep the bundle's `## Verify` blocks for the "
    "files you changed this turn (e.g. `grep -A3 '## Verify' <bundle>/*.md`); for each concept that names "
    "a changed file, dispatch the `wiki-verifier` subagent in the background with the concept path and "
    "bundle root. "
    "(3) If nothing durable changed this turn, just stop — do not invent a finding."
)


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    if event.get("stop_hook_active"):
        return 0  # already nudged once this turn — allow the stop (loop guard)
    project = _hook_common.project_dir(event)
    if not _hook_common.bundle_exists(project):
        return 0  # no bundle here — contribute nothing

    marker = _hook_common.capture_marker(project)
    if not os.path.exists(marker):
        return 0  # no real-code edit this turn (PostToolUse drops the marker) — stay silent
    try:
        os.remove(marker)  # consume it — nudge at most once per change-batch
    except OSError:
        pass

    json.dump({"decision": "block", "reason": NUDGE}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
