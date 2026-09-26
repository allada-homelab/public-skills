---
type: gotcha
title: Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact
description: To re-inject wiki context after compaction, branch the SessionStart hook on source compact; a PreCompact hook is the wrong tool because its output may be folded into the compaction summary.
tags: [hooks, autonomy, compaction, llm-wiki]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: commit:94a1f53, title: capture post-compaction re-injection concept}
  - {id: s2, resource: plugins/llm-wiki/scripts/hook_session_start.py, title: SessionStart hook with the compact branch}
  - {id: s3, resource: plugins/llm-wiki/hooks/hooks.json, title: hook wiring}
---

# Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact

## Symptom

A long session compacts and the preloaded wiki catalog is gone. The obvious fix is a `PreCompact`
hook that re-injects the concept map.

## What fails

A `PreCompact` hook. The Claude Code docs do not confirm that PreCompact's
`hookSpecificOutput.additionalContext` survives into the post-compaction window. It runs before
compaction, so what it emits is subject to the compaction it precedes and may end up only in the
summary. Re-injection built on it is unverified and likely silently ineffective[^s1].

## What works

The existing `SessionStart` hook already covers it. `hooks.json` registers SessionStart with no
`matcher`, which means match-all, so it fires on startup, resume, clear **and** `compact`[^s3].
`hook_session_start.py` branches on `source == "compact"`[^s2]:

- It emits a lighter payload: the concept summary, the consult guidance and the session ids, plus
  a pointer to re-read the recursive indexes. It skips the full catalog so it does not partly undo
  the compaction or grow with the bundle.
- It skips the stale capture-marker sweep, because a compaction is the same session continuing.

To strengthen post-compaction recall, edit that branch. Do not add a PreCompact hook, and do not add
a `matcher` to the SessionStart entry, which would silently drop the compact case.

## Why

SessionStart-on-compact output is the documented channel for putting text into the freshly
compacted window. PreCompact has no such guarantee.

## Verify

- `plugins/llm-wiki/scripts/hook_session_start.py` :: `if event.get("source") == "compact":`
- `plugins/llm-wiki/hooks/hooks.json` :: /"SessionStart": \[\s*\{\s*"hooks"/ => 1
- `plugins/llm-wiki/hooks/hooks.json` :: /PreCompact/ => 0
