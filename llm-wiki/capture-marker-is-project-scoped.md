---
type: gotcha
title: Capture marker is session-scoped — a phantom Stop nudge means a stale, foreign, or deferred marker
description: The Stop-hook capture nudge is gated by a marker named `capture-pending-<session_id>` (since 2026-07-04; it was one project-wide path before, which let concurrent/headless Claude processes arm another session's nudge). A nudge on a no-change turn now means either a legacy unsuffixed marker (no-session_id CLI fallback) or the by-design one-turn deferral when another Stop hook blocked the previous cycle — and "Stop hook error" is Claude Code's normal rendering of ANY blocking Stop hook, not a crash.
tags:
  - gotcha
  - hooks
  - autonomy
---

# Capture marker is session-scoped — a phantom Stop nudge means a stale, foreign, or deferred marker

Facts for diagnosing "the llm-wiki Stop hook errored on a turn where nothing changed":

1. **"Stop hook error:" is Claude Code's normal rendering for any blocking Stop hook.** Both blocking channels — `exit 2` + stderr, and the `{"decision": "block", "reason": ...}` JSON that `hook_stop.py` emits — display under that label. It is the blocking channel working as designed, not a script crash.

2. **The marker is session-scoped (fixed 2026-07-04).** It was originally one fixed per-project path (`<bundle>/.llm-wiki/capture-pending`), so any concurrent Claude process in the project dir — a headless background job, a parallel session — could arm *another* session's nudge, and a killed session's stale marker fired on the next session's first stop (both observed live in this repo). The fix: `_hook_common.capture_marker(project, session_id)` appends the sanitized event `session_id` (`capture-pending-<session_id>`), `hook_post_tool.py` drops and `hook_stop.py` consumes only their own session's marker, and the SessionStart hook sweeps stale markers (legacy unsuffixed ones immediately, session-scoped ones older than a day; skipped on `source == "compact"`). On a CLI that sends no `session_id`, both hooks fall back to the legacy unsuffixed name so producer and consumer still pair.

3. **Subagent tool calls carry the parent session's `session_id`** (empirically verified 2026-07-04 with a hook-logging probe: a general-purpose subagent's Write, the main loop's Write, SubagentStop, and Stop all reported one identical `session_id`; a headless `claude -p` run got its own fresh id — the docs don't specify this). So a subagent's real code edit arms its *own session's* marker, which that session's Stop consumes — session scoping loses no nudges to subagents.

4. **One-turn deferral is by design.** `hook_stop.py` checks `stop_hook_active` *before* the marker, so when a different Stop hook blocked the previous cycle, the nudge survives and fires on the next stop — one turn late, possibly on a pure-chat turn. Deliberate trade-off: a late nudge beats a lost capture.

## Verify

- `plugins/llm-wiki/scripts/_hook_common.py` — `capture_marker()` appends `-<sanitized session_id>` when given one; the unsuffixed name is only the no-session_id fallback.
- `plugins/llm-wiki/scripts/hook_stop.py` — the marker path is built with the event's `session_id`, and the `stop_hook_active` early-return precedes the marker check.
- `bash plugins/llm-wiki/scripts/hook_fixtures/run_hooks.sh` → `fail=0`, and the corpus contains `stop_foreign_marker_silent` and `session_start_sweeps_stale_markers`.
