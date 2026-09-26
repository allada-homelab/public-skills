---
type: decision
title: get-shit-done and minimalist-code-review are frozen copies here
description: Change get-shit-done and minimalist-code-review in agent-harness-marketplace, not here; the copies in this repo are frozen, and nothing inside their plugin dirs says so.
tags: [marketplace, plugins, distribution]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: https://github.com/allada-homelab/public-skills/pull/3, title: PR 3 moved the two plugins}
  - {id: s2, resource: commit:7ea6868, title: marketplace and README pointer}
  - {id: s3, resource: .claude-plugin/marketplace.json, title: marketplace manifest}
---

# get-shit-done and minimalist-code-review are frozen copies here

## Decision

On 2026-09-06 `get-shit-done` and `minimalist-code-review` moved to
https://github.com/allada-homelab/agent-harness-marketplace, where one content tree installs
natively on Claude Code, pi and dsh[^s1]. The copies under `plugins/` here still install from this
marketplace but receive no further changes[^s2]. A fix or feature for either plugin belongs in that
repo. Only `llm-wiki` (and the unregistered `llm-wiki-optimizer` harness) is still developed here.

## Why

This matters because the only markers are the root `README.md` "Moved" note and the two
`marketplace.json` descriptions ("Frozen here")[^s3]. An agent sent straight to
`plugins/get-shit-done/` or `plugins/minimalist-code-review/` sees no warning and would edit a
dead copy.

## Rejected alternatives

- Deleting the copies. That would break existing `@public-skills` installs.
- Keeping two live copies. They would drift. The move exists to have one source of truth.

## Revisit when

The README says `llm-wiki` stays here "until its successor (`okf-wiki`) ships there". okf-wiki now
ships from agent-harness-marketplace, so check whether `llm-wiki` should be frozen or retired the
same way, and whether these frozen copies can be dropped from the marketplace.

## Verify

- `.claude-plugin/marketplace.json` :: `Frozen here: maintained in allada-homelab/agent-harness-marketplace`
- `README.md` :: `will not receive further changes`
