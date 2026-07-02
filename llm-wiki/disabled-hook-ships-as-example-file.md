---
type: gotcha
title: A toggleable plugin hook ships as a disabled .example.json, not a commented-out hook
description: hooks.json is strict JSON (no comments) and a plugin's live hooks.json loads wholesale, so a hook you want present-but-off can't be commented out — ship it as a separate hooks/<name>.example.json plus its script, enabled by copying to hooks.json (dropping the _comment key) and running /reload-plugins.
tags:
  - hooks
  - plugin
  - convention
  - gotcha
  - marketplace
timestamp: 2026-07-02
---

# Disabled/toggleable plugin hook → ship a `.example.json`, not a comment

When a Claude Code plugin should ship a hook that is **present but off** (so the user can enable it later), you cannot "comment it out": `hooks/hooks.json` is **strict JSON** (rejects `//` and `/* */`), and a plugin's live `hooks.json` is loaded wholesale — there is no per-entry disable flag.

**Convention (used by the `get-shit-done` plugin):** ship the disabled hook as a separate `hooks/<name>.example.json` alongside its script under `scripts/`, carrying a `_comment` key that explains how to turn it on. Enable by **copying** the example to `hooks/hooks.json` (dropping `_comment`, since the live file is strict JSON) and running `/reload-plugins`. The plugin ships with **no live `hooks.json`** until the user opts in — so the feature is fully authored and reviewable in-repo while defaulting to off.

This is the mechanism behind get-shit-done's "explicit-only now, auto-trigger later" invocation model.

## Verify

- `plugins/get-shit-done/hooks/auto-trigger.example.json` — the disabled hook config; note the `_comment` enable instructions and that no live `plugins/get-shit-done/hooks/hooks.json` exists.
- `plugins/get-shit-done/scripts/gsd_autotrigger.py` — the detector script the example wires.
- `plugins/get-shit-done/README.md` — the "Auto-trigger (optional, off by default)" enable steps.

verified: 2026-07-02
