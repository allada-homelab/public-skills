---
type: Gotcha
title: Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact
description: To re-inject wiki context after a compaction, branch the SessionStart hook on source=="compact" — a PreCompact hook is the wrong tool (its additionalContext may not survive compaction).
tags:
  - hooks
  - autonomy
  - gotcha
timestamp: 2026-06-26T00:00:00Z
verified: 2026-07-04
---
# Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact

**Symptom / context.** A long session compacts its context and the preloaded wiki index is
dropped. The instinct is to add a `PreCompact` hook to re-inject the concept map so the model
still has it afterward.

**What does not work.** A `PreCompact` hook. The Claude Code docs do not confirm that
`PreCompact`'s `hookSpecificOutput.additionalContext` survives *into* the post-compaction context
window — it may be consumed into the summary the compaction produces. Re-injection built on that
channel is unverified and likely silently ineffective.

**What works.** The existing `SessionStart` hook already covers it. `hooks.json` registers
SessionStart with **no matcher**, and per the docs an omitted matcher = "match all", so SessionStart
fires on `source` startup/resume/clear **and** `compact` (auto or manual). `hook_session_start.py`
branches on `event.get("source") == "compact"` and injects a deliberately lighter payload — mode
notice + concept count + tags + a "re-read the index" pointer — instead of the full index body, so it
does not partially undo the compaction or grow unbounded with the bundle. To strengthen
post-compaction recall, edit that branch; do not add a new hook.

**Why.** `SessionStart`-on-compact stdout / `additionalContext` is the documented,
survival-guaranteed channel for landing text in the freshly-compacted window. `PreCompact` runs
*before* compaction, so anything it emits is subject to the very compaction it precedes.

## Verify
- plugins/llm-wiki/hooks/hooks.json — SessionStart block has no `matcher` (match-all → fires on `compact`)
- plugins/llm-wiki/scripts/hook_session_start.py:148-151 — the `source == "compact"` branch
- plugins/llm-wiki/scripts/hook_fixtures/session_start_compact/ — unit-tests the compact payload

## Related
- See [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the six wired hook events this refines.
