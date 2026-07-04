---
type: gotcha
title: PostToolUse fires for subagent tool calls and /tmp writes — broad markers self-arm
description: Claude Code hooks fire for background subagents' tool calls too, and a PostToolUse marker keyed on "any Write/Edit outside the bundle" counts /tmp scratch writes — so llm-wiki's own wiki-capturer (which drafts to /tmp) re-armed the Stop-hook capture nudge, producing phantom "nothing durable — stopping" turns; scope such markers to files under the project dir.
tags:
  - gotcha
  - hooks
  - autonomy
  - subagents
timestamp: 2026-07-04
---

# PostToolUse fires for subagent tool calls and /tmp writes — broad markers self-arm

Observed live: the llm-wiki Stop-hook nudge fired repeatedly on turns where the user's session
changed no code. Root cause, two stacked facts that are easy to miss:

1. **Hook events fire for background subagents' tool calls too**, not just the main loop's. A
   dispatched `wiki-capturer` / `wiki-verifier` doing its work generates PostToolUse events in the
   same project.
2. `hook_post_tool.py` originally dropped the `capture-pending` marker for **any** Write/Edit whose
   path was merely *outside the bundle* — which includes `/tmp`. The capturer drafts its concept to a
   `mktemp` file in `/tmp` before applying, so **the wiki's own capture machinery re-armed the
   capture nudge**: capture → subagent /tmp write → marker → next stop blocked → "nothing durable —
   just stop" → repeat.

The fix: scope the marker to files **under the project dir** (realpath both sides) *and* outside the
bundle — "real project code changed" is the actual trigger condition. An `agent_id`-based guard
(subagent events carry one) was considered and rejected as primary: it would also silence legitimate
code-writing subagents and relies on a field with a propagation-bug history (cf. `stop_hook_active`,
Claude Code issue #54360).

General rule: any hook-driven marker keyed on "a write happened" must define the trigger set
positively (under the project, outside the tool's own state dirs), or the tool's own background
machinery will trip it.

## Verify

- `plugins/llm-wiki/scripts/hook_post_tool.py` — the marker-drop path requires the written file to be
  under the project dir (not merely outside the bundle) before creating the session-scoped
  `capture-pending-<session_id>` marker (`_hook_common.capture_marker`; falls back to the unsuffixed
  `capture-pending` name only when the event carries no `session_id`).
