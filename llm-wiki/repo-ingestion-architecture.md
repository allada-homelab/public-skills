---
type: Architecture Decision
title: Repo ingestion — orchestrated multi-agent bootstrap
description: How /llm-wiki:ingest bootstraps a wiki from an existing repo — an orchestrator command fans out read-only Sonnet wiki-explorer subagents that return concept proposals, then writes one Doctor-gated autonomous batch.
tags:
  - ingestion
  - orchestration
  - subagents
timestamp: 2026-06-15T00:00:00Z
---
# Repo ingestion — orchestrated multi-agent bootstrap

`/llm-wiki:ingest [repo-path] [--scope min|medium|high] [--dry-run]` populates an **existing** bundle
from a whole repository. The command is the **orchestrator**; the read-only `agents/wiki-explorer.md`
subagent (Sonnet) is the unit it fans out.

## The loop

1. **Recon** (orchestrator, cheap): README, layout, manifests, CI, `docs/`; also load existing concepts
   to dedupe against.
2. **Partition** the repo into work units sized by `--scope` (the scope→budget table lives in
   `skills/wiki/references/ingestion.md`).
3. **Fan out** one `wiki-explorer` per unit, in parallel. Each explores its slice **read-only** and
   returns structured concept proposals (a JSON block: type/title/slug/description/tags/links/sources/
   body) — it never writes.
4. **Synthesize** (orchestrator): dedupe across subagents and against existing concepts; choose
   structure **flat-first** (a subdir section only for a real ~3+ cluster — never a lonely folder);
   assign final paths + frontmatter; resolve cross-links to real `./` paths.
5. **Write one batch** through the staged-mirror → `bundle_ops` → Doctor-gate flow, then report.

## Decisions

- **Command, not an auto-skill.** Ingestion is an expensive, deliberate, one-time action — explicit
  invocation (consistent with the other commands), so it never auto-fires mid-task.
- **Autonomous once invoked** (no per-concept confirm gate) — the single deliberate exception to the
  confirm-first rule. The floor still holds: every concept is **secret-scanned** in the mirror (a hit is
  redacted, since the `cp`-back bypasses the PreToolUse `secret_guard`), the whole batch is
  **Doctor-gated** before it lands, and the result is one **git-reversible** diff. `--dry-run` previews
  the plan without writing.
- **`--scope`** trades breadth for cost: `min` (seed) / `medium` (default, curated) / `high`
  (exhaustive, hard-capped, drops logged — never truncate silently).
- **No new deterministic code.** Ingest composes the already-tested `bundle_ops` / `doctor` /
  `secret_scan` primitives, so it adds no fixtures of its own.

## Related
- [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the same guard-floor reasoning that makes an autonomous ingest safe.
