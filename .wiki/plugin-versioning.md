---
type: decision
title: Plugin versioning — pinned; every user-visible change requires a version bump
description: plugin.json pins version, so installed users get an update only when it is bumped; a push without a bump strands them on the stale cache while /plugin reports already at the latest version.
tags: [versioning, distribution, plugin, llm-wiki]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: commit:7939ecc, title: bump to 0.1.1 so installed users receive the fix batch}
  - {id: s2, resource: commit:56581ee, title: original unpinned-version decision}
  - {id: s3, resource: https://github.com/allada-homelab/public-skills/pull/4, title: PR 4 bumped 0.2.0 to 0.2.1 alongside its fix}
---

# Plugin versioning — pinned; every user-visible change requires a version bump

## Decision

`plugins/llm-wiki/.claude-plugin/plugin.json` pins an explicit `version`. Treat the manifest as
the source of the current number, and don't cite it in prose. **Any commit that changes plugin
behavior bumps `version` in the same commit or PR**, as PR 4 did for its fix[^s3].

## Why

With `version` set, Claude Code keys the plugin cache by that string and `/plugin` compares
version strings. It does not compare commits. On 2026-07-17 a fix batch was pushed to `main`
without a bump. `/plugin` reported that llm-wiki was already at the latest version and never
refetched, and `/reload-plugins` reloaded the stale cache, so installed hooks kept running the old
code until 7939ecc bumped to 0.1.1[^s1]. Nothing errors when this happens.

## Rejected alternatives

- **Omit `version`**, the original choice[^s2]. Claude Code then falls back to the git commit SHA,
  so every push auto-updates installed users with no release ceremony. It was dropped for a
  steadier release cadence. The cost of pinning is the bump discipline above.

## Revisit when

The plugin goes back to unpinned SHA updates, or Claude Code starts comparing source commits for
pinned plugins.

## Verify

- `plugins/llm-wiki/.claude-plugin/plugin.json` :: /"version":/ => 1
