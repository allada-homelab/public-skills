---
type: gotcha
title: A phantom or noisy llm-wiki Stop nudge comes from Claude Code hook runtime facts
description: Hooks fire for subagent tool calls with the parent session_id, and a blocking Stop reason always renders as "Stop hook error"; scope write markers per session and in-project, keep the reason short.
tags: [hooks, autonomy, subagents, llm-wiki]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:47Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:47Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: commit:250dfe2, title: session-scope the capture marker}
  - {id: s2, resource: commit:dcf4056, title: scope the marker to project files}
  - {id: s3, resource: commit:1c8a42c, title: pass Stop-hook requests by path}
  - {id: s4, resource: llm-wiki/posttooluse-fires-for-subagents-and-tmp.md, title: dogfood concept on the /tmp self-arm loop}
---

# A phantom or noisy llm-wiki Stop nudge comes from Claude Code hook runtime facts

## Symptom

The llm-wiki Stop hook blocks on a turn where the user's session changed no code, or blocks over and
over. Or the transcript shows "Stop hook error:" followed by kilobytes of JSON.

## What fails

- **Hooks fire for subagents' tool calls too.** A PostToolUse marker keyed on "any write outside
  the bundle" was armed by the plugin's own `wiki-capturer`, which drafts to `/tmp`. The result was
  a loop: capture, `/tmp` write, marker, blocked stop, "nothing durable", and again[^s2][^s4].
- **Subagent events carry the parent's `session_id`.** A hook-logging probe on 2026-07-04 saw the
  main loop's Write, a subagent's Write, SubagentStop and Stop all report one id. A headless
  `claude -p` run got a fresh id. The docs don't say this[^s1].
- **A project-wide marker path** let a parallel session or a background job arm another session's
  nudge. A killed session's stale marker also fired on the next session's first stop[^s1].
- **The blocking Stop `reason` always renders** in the TUI, and `suppressOutput` does not hide it.
  Claude Code labels every blocking Stop hook "Stop hook error:", even when nothing crashed. Inlining
  the request packet dumped about 4.5k characters per cycle[^s3].

## What works

- The marker is `capture-pending-<session_id>`. It is dropped only for writes under the project
  dir and outside the bundle, and never for `llm-wiki:*` agents. SessionStart sweeps stale markers
  but skips the sweep on `compact`.
- The Stop reason carries a path to the request packet under the bundle's session state, not the
  packet. It inlines the packet only if writing that file fails.
- Two by-design delays can look like phantoms. `stop_hook_active` returns before the marker check,
  so when another Stop hook blocked the previous cycle, the nudge fires one turn late. And a marker
  below `capture_min_edits` stays in place and adds up over turns.

## Why

A marker meaning "this session changed real code" must define that set positively:
this session, this project, not the tool's own state or agents. Otherwise the tool's own
background machinery, or a neighbouring session, trips it. An `agent_id` guard was rejected as
the main fix because it would also silence real code-writing subagents.

## Verify

- `plugins/llm-wiki/scripts/_hook_common.py` :: `name += "-" + _SESSION_ID_UNSAFE.sub("_", str(session_id))`
- `plugins/llm-wiki/scripts/hook_post_tool.py` :: `agent_type.startswith("llm-wiki:")`
- `plugins/llm-wiki/scripts/hook_stop.py` :: `def _write_request`
- `plugins/llm-wiki/scripts/hook_stop.py` :: `if event is None or event.get("stop_hook_active"):`
