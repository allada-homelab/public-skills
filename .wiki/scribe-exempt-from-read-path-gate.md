---
type: decision
title: wiki-capturer is deliberately outside the read-path gate
description: Leave wiki-capturer out of hook_pre_read's _PROTECTED_AGENTS; it must Read its own /tmp request and prepared files, which the gate's outside-the-project rule would deny.
tags: [hooks, security, subagents, llm-wiki]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: https://github.com/allada-homelab/public-skills/pull/4, title: PR 4 notes on the capturer read gate}
  - {id: s2, resource: plugins/llm-wiki/agents/wiki-capturer.md, title: capturer prompt with literal /tmp paths}
  - {id: s3, resource: plugins/llm-wiki/scripts/hook_pre_read.py, title: read-path policy}
---

# wiki-capturer is deliberately outside the read-path gate

## Decision

`hook_pre_read.py` confines the read-only reasoning agents (verifier, explorer, sentinel, glimmer,
archaeologist, compiler, researcher, ...) to in-project, non-credential paths. `wiki-capturer`, the
background Wiki Scribe, is intentionally **not** in `_PROTECTED_AGENTS`, even though its tool list
now includes `Read, Grep, Glob`[^s1][^s3].

## Why

The Scribe's pipeline is built on `/tmp`: it Writes `/tmp/<request>.json`, runs `publication.py`
to produce `/tmp/<prepared>.md`, and then feeds that to `bundle_ops.py apply`[^s2]. It has to Read
those files back. The read gate denies any path outside the project dir, so adding the capturer to
the protected set would make every Scribe run fail its first Read and burn its 12-turn budget with
no result. That exact symptom was what PR 4 fixed from the Bash side[^s1]. The capturer's power is
bounded elsewhere instead: `hook_pre_write.py` limits its Write to secret-scanned `/tmp` staging,
and `hook_pre_bash.py` allows only the two fixed publication/apply commands.

## Rejected alternatives

- Add the capturer to `_PROTECTED_AGENTS` for symmetry with the other agents. This breaks the
  `/tmp` round-trip described above.
- Move staging inside the project. That puts transient drafts in the user's working tree and
  `git status`, and the write guard's `/tmp`-only staging rule would need its own carve-out. It
  was never attempted. Staging outside the project also fits
  [the hook marker scoping](./stop-nudge-hook-runtime-facts.md).

## Revisit when

The Scribe no longer stages through `/tmp`, or the read gate learns a narrow `/tmp` allowance for
paths the job controller issued.

## Verify

- `plugins/llm-wiki/scripts/hook_pre_read.py` :: /"wiki-capturer"/ => 0
- `plugins/llm-wiki/scripts/hook_pre_read.py` :: `_PROTECTED_AGENTS = frozenset`
- `plugins/llm-wiki/agents/wiki-capturer.md` :: `/tmp/<prepared>.md`
