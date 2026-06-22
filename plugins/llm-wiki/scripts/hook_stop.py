#!/usr/bin/env python3
"""Stop hook — the end-of-turn capture forcing function (reliable auto-capture trigger).

The UserPromptSubmit / PostToolUse nudges fire *mid-turn*, where the model tends to defer
capture in favour of the in-flight task, so durable findings slip by uncaptured. This hook
fires when the turn is *finishing* — the non-disruptive moment to capture — and, in an auto
mode, blocks the stop once to make the model actually decide: capture a durable finding now,
or explicitly stop.

Mechanism (Claude Code Stop-hook contract): emit `{"decision": "block", "reason": ...}` at exit
0 to continue the turn with the reason injected; emit nothing to allow the stop. (The doc names
`decision: "block"` + `reason` as the canonical Stop blocking channel, so we emit only that — no
redundant `hookSpecificOutput.additionalContext` carrying the same text.) Gated by the
`.llm-wiki/capture-pending` marker that the PostToolUse hook drops on a real-code edit: with no
marker (a pure-chat turn that changed nothing) this hook stays silent, so it does not force a
continuation on every turn. Also silent for curated mode and when no bundle exists. Reads
`$CLAUDE_PROJECT_DIR` (falls back to the event JSON's `cwd`).

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

from mode import resolve_mode

NUDGE = (
    "[llm-wiki] Before finishing this turn: if it established a durable, reusable finding (a "
    "decision; a gotcha — e.g. a silent footgun, a surprising root cause, or a failure->fix where "
    "one approach failed and another worked; a convention, schema, or how something works), capture "
    "it to the wiki now via /llm-wiki:capture — it is secret-scanned, Doctor-gated, logged, and "
    "git-reversible. In an auto mode apply it silently: do not announce or summarize what you saved. "
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

    marker = os.path.join(project, "llm-wiki", ".llm-wiki", "capture-pending")
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
