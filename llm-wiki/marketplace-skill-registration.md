---
type: Convention
title: Registering a skill in the public-skills marketplace
description: How to add a standalone skill to this marketplace — the manifest registers plugins (not skills directly), so a skill ships inside a plugin under plugins/<name>/skills/.
tags:
  - distribution
  - plugin
  - marketplace
  - skills
generated: { by: llm-wiki/unknown, at: 2026-06-25T00:00:00Z }
verified:
  - { by: llm-wiki/unknown, at: 2026-07-17T00:00:00Z }
  - { by: llm-wiki/claude-opus-5, at: 2026-07-30T02:56:20Z }
---
# Registering a skill in the public-skills marketplace

The marketplace manifest (`.claude-plugin/marketplace.json`) registers **plugins, not
skills directly**. A skill ships *inside* a plugin at `skills/<skill-name>/SKILL.md`. So
"add a skill to the marketplace" always means "create or extend a plugin that houses it".

## Steps to add a standalone skill

1. Create `plugins/<plugin-name>/.claude-plugin/plugin.json` — set an explicit `version`
   and bump it on every user-visible change (see related; the earlier omit-for-SHA-updates
   convention was reversed 2026-07-17).
2. Place the skill at `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` (plus any
   `references/`).
3. Add an entry to the `plugins` array in `.claude-plugin/marketplace.json`:
   `{ "name", "description", "category", "source": "./plugins/<plugin-name>" }`.
4. Document it in `README.md`: a plugin section, an install line
   (`/plugin install <plugin-name>@public-skills`), and the repo-layout tree.

## Plugin name need not match the skill name

A plugin is an **umbrella** that can hold multiple related skills, so name the plugin for
the family, not the single skill. Example (verified 2026-06-25): the plugin
`minimalist-code-review` houses the skill `pragmatic-code-review`.

## Verify
- .claude-plugin/marketplace.json — registers plugins (not skills directly) via a `plugins` array
- run: `python3 -c "import json;print('plugins' in json.load(open('.claude-plugin/marketplace.json')))"` — expected: `True`

## Related
- [Plugin versioning — pinned; every user-visible change requires a version bump](./plugin-versioning.md) — why `version` is pinned and must be bumped per change.
