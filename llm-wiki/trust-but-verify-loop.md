---
type: Convention
title: Reading is trust-but-verify — the consult-then-confirm loop
description: Trust a wiki finding on its face, but cheaply confirm load-bearing claims against current state via a ## Verify anchor + freshness gate, with background self-healing verification.
tags:
  - reading
  - verification
  - autonomy
  - convention
generated: { by: llm-wiki/unknown, at: 2026-06-26T21:47:23Z }
verified: { by: llm-wiki/unknown, at: 2026-06-28T05:51:41Z }
---
# Reading is trust-but-verify — the consult-then-confirm loop

The wiki is a **somewhat-trusted summary** (curated, Doctor-gated, cross-linked), not an oracle and not
an unproven hypothesis to re-derive. Posture: **high prior, cheap check** — trust a finding and use it
now, but before *acting* on a load-bearing one, confirm it still holds against current state at the spot
the concept points to. Trust the summary; verify the spot — don't re-investigate.

## How it works (paired change: capture ⇄ read)

- **Capture records the anchor.** Each code-grounded concept carries a `## Verify` section — a *checkable*
  pointer: a resolvable `file:symbol` or a runnable `run: <cmd> — expected: <result>`. Free-form text,
  **not a markdown link**; repo-root-relative; never prose-only ("see the code") or a bare `file:line`
  (line numbers rot). Plus a `verified:` frontmatter stamp (when it was last confirmed). Both
  `/llm-wiki:capture` and `/llm-wiki:ingest` (via the `wiki-explorer`'s `verify` output) produce them;
  a genuinely non-code-verifiable concept is confirm-exempt (omit both, note "not code-verifiable").
- **Read confirms cheaply.** `/llm-wiki:query` trusts the answer on its face, then for load-bearing claims
  runs a sync **freshness gate** — `git log --since=<verified> -1 -- <anchor-file>`. Empty → trust, do
  nothing. Changed → dispatch a background **`wiki-verifier`** subagent (Sonnet) so the main loop never
  blocks; escalate to an inline check only for an act-now-high-stakes claim or a quick `run:` anchor.
- **Self-heal is guarded.** The verifier returns confirmed / stale (+why) / couldn't-verify, and rewrites
  the concept (gated self-heal via `apply`) **only on objective `run:` divergence** — never on a cheap model's prose
  judgment, which it only *reports*. Self-heals surface one line; never silent.
- **`/llm-wiki:tend`** adds the proactive bundle-wide freshness sweep (same git gate) + flags weak/missing
  anchors on code-grounded concepts.

## Why

The win is that the anchor makes confirmation a *targeted glance*, not a re-investigation — that is what
keeps "verify" cheap enough to always do. Read-time confirmation is cheap **only because** capture
recorded a good anchor; that is why the two halves ship together. Background + cheap-model verification
keeps the main loop fast and lets the wiki self-heal over time, at the cost that an action taken on the
trusted-on-face value isn't retro-protected (the inline escalation is the escape hatch for that).

## Verify
- plugins/llm-wiki/skills/wiki/SKILL.md — the "Reading is trust-but-verify" and "Verify anchors" sections state this convention
- plugins/llm-wiki/commands/query.md — step 5 (trust-but-verify: freshness gate + dispatch)
- plugins/llm-wiki/agents/wiki-verifier.md — the background verifier + objective-divergence self-heal
- run: `grep -c "Reading is trust-but-verify" plugins/llm-wiki/skills/wiki/SKILL.md` — expected: 1

## Related
- See [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) — the autonomy model this reading discipline sits inside.
