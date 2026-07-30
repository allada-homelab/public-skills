---
type: gotcha
title: Dispatch gate resolves jobs by feature fallback — never require the id in text
description: hook_pre_dispatch authorizes protected recall/worker dispatches from controller-issued jobs, but requiring the job id to appear literally in tool_input text dead-ended real sessions (dropped envelope, older ids quoted for context); since 0.1.2 the gate falls back to the unique startable job of the target feature, and denies are diagnostic, not opaque.
tags:
  - autonomy
  - hooks
  - dispatch
  - gotcha
generated: { by: llm-wiki/unknown, at: 2026-07-17T00:00:00Z }
verified: { by: llm-wiki/unknown, at: 2026-07-17T00:00:00Z }
---
# Dispatch gate resolves jobs by feature fallback — never require the id in text

`hook_pre_dispatch.py` gates protected llm-wiki dispatches (the recall skill family and the
worker agents) on a controller-issued job. Originally `dispatch.select_job` authorized only
when **exactly one** feature-matching `job-<20hex>` id appeared literally in the dispatch's
`tool_input` strings. Field use broke this twice on 2026-07-17:

- a model-initiated `llm-wiki:recall` with no candidate envelope (no id anywhere) — denied,
  even though the plugin's own guidance says to consult the wiki proactively;
- a sentinel dispatch that followed the Stop-hook instruction verbatim — denied, plausibly
  from an older cycle's job id quoted alongside the current one (two matches → refuse).

Both produced the same opaque deny, and the orchestrator had no recovery path.

## The rule (since plugin 0.1.2)

When the id-scan does not resolve to exactly one job, `select_job` falls back to **the unique
startable job of the target feature** in the session store (pending, unexpired, same
`run_id`). This grants no new authority — the job was controller-issued, feature-matched,
budget-reserved, and session-scoped either way; only the resolution mechanism changed.
Ambiguity (two startable jobs of one feature) still denies: never guess. Deny messages are
diagnostic and actionable — recall denies redirect to the ungated read-only `/llm-wiki:query`;
worker denies name the job state and say *skip, do not retry*.

Do not "harden" this back to text-only id matching: any design that requires a model to
round-trip an exact token through prose will meet the model that paraphrases it.

## Verify
- plugins/llm-wiki/scripts/dispatch.py — `_startable_fallback` + `select_job` falling back on failed/ambiguous id-scan
- run: `grep -c "_startable_fallback" plugins/llm-wiki/scripts/dispatch.py` — expected: `2` (definition + call)

## Related
- [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) — the hook architecture this gate belongs to.
- [Plugin versioning — pinned; every user-visible change requires a version bump](./plugin-versioning.md) — the 0.1.2 release that shipped this rule.
