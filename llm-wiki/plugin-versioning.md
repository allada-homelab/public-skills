---
type: decision
title: Plugin versioning — pinned; every user-visible change requires a version bump
description: plugin.json now pins version, so updates only reach installed users on an explicit bump — forgetting one silently strands users on a stale cache while /plugin reports "already at the latest version".
tags:
  - versioning
  - distribution
  - plugin
timestamp: 2026-06-15T00:00:00Z
verified: 2026-07-17T00:00:00Z
---
# Plugin versioning — pinned; every user-visible change requires a version bump

`plugins/llm-wiki/.claude-plugin/plugin.json` **pins an explicit `version`** (the manifest is
the authority for the current number — this concept deliberately does not cite it). Per the Claude Code plugins reference: a set `version` pins the plugin to that
string, so installed users only receive updates when it is bumped; the plugin cache is keyed
by that version (`~/.claude/plugins/cache/public-skills/llm-wiki/<version>/`).

## The gotcha (observed 2026-07-17)

Pushing plugin changes **without** bumping `version` strands every installed user on the old
build *silently*: `/plugin` compares version strings, reports "llm-wiki is already at the
latest version (0.1.0)", and never refetches — `/reload-plugins` then reloads the stale
cache. This bit us the same day the fix batch for the homelab bug report was pushed: the
commits landed on `main` but the installed hooks kept running the old code.

**Rule: any commit that changes plugin behavior must bump `version` in the same commit.**

## History

The plugin originally *omitted* `version` deliberately — Claude Code then falls back to the
git commit SHA and every push auto-updates installed users (zero release ceremony during
active development; older SHA-named cache dirs still exist alongside the versioned one).
Pinning was the planned reversal for a stabler cadence, but the bump-on-change discipline is
the non-optional other half of that trade.

## Verify
- plugins/llm-wiki/.claude-plugin/plugin.json — explicit `version` field present
- run: `grep -c '"version"' plugins/llm-wiki/.claude-plugin/plugin.json` — expected: `1`

## Related
- [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — another plugin-architecture decision recorded for its "why".
