---
type: decision
title: Plugin versioning — unpinned for git-SHA auto-update
description: Why plugin.json omits the version field — Claude Code falls back to the git commit SHA, so every commit auto-updates installed users during active development.
tags:
  - versioning
  - distribution
  - plugin
timestamp: 2026-06-15T00:00:00Z
verified: 2026-06-26T21:36:34Z
---
# Plugin versioning — unpinned for git-SHA auto-update

`plugins/llm-wiki/.claude-plugin/plugin.json` deliberately **omits** the `version`
field. Per the Claude Code plugins reference: setting `version` pins the plugin to that
string, so users only receive updates when you bump it; if it is omitted, Claude Code
**falls back to the git commit SHA** and treats every commit as a new version.

## The decision

While the plugin is under active development, leave `version` unset. Every push to `main`
then auto-updates everyone who installed `llm-wiki@public-skills` — no manual bump step,
and no risk of silently stranding users on an old build because a release was forgotten.

## Trade-off (why this isn't free)

- **Gained:** zero release ceremony; the marketplace always serves the latest commit.
- **Cost:** more frequent version churn for users (every commit is "a new version"), and no
  human-readable semantic version to reference in a changelog or bug report.

## When to reverse it

Re-introduce an explicit `version` (and pair it with a CHANGELOG / release checklist) once
the plugin stabilizes and updates should land on a deliberate cadence rather than per commit
— i.e. when "every commit ships to users" stops being desirable.

## Verify
- plugins/llm-wiki/.claude-plugin/plugin.json — no `version` field present (omitted deliberately for git-SHA auto-update)
- run: `grep -c '"version"' plugins/llm-wiki/.claude-plugin/plugin.json` — expected: `0`

## Related
- [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — another plugin-architecture decision recorded for its "why".
