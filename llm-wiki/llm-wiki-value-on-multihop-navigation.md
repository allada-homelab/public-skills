---
type: Decision
title: llm-wiki value shows on multi-hop navigation, not single-hop grep lookups
description: An end-to-end optimizer experiment found the wiki's measurable retrieval uplift concentrates on multi-hop new-developer navigation (finding the full set of files for a change), not single-hop grep-able lookups where a strong agent already wins.
tags:
  - optimizer
  - evaluation
  - retrieval
verified: 2026-06-28
---
# llm-wiki value shows on multi-hop navigation, not single-hop grep lookups

The first end-to-end run of the self-optimizer harness (over the private `agents-scaffold` repo, a
blind architecture wiki, a Sonnet SUT with-wiki vs wiki-ablated) gave a clear, actionable result:

- **Single-hop Locate — "where is `X` defined?" — is grep-trivial.** A grep-capable agent already
  scores ~0.97 F1 *without* the wiki, so the wiki adds ~**+0.03** (noise) and every read-prompt
  candidate ceilings out. Single-hop is a poor discriminator — it can measure neither the wiki's value
  nor a prompt's quality.
- **Multi-file "new-developer change-set" tasks — "which source files are involved in ⟨this change⟩?"
  — are where the wiki earns its keep.** Mean uplift **+0.083**, and **strongly inverse to
  difficulty**: ~0 where the no-wiki baseline is already high (nameable, localized), but **+0.14 to
  +0.32 on the low-baseline items** where a developer must connect scattered files across subsystems.

## Why

The identifier is *in* a single-hop question, so grep shortcuts it. A change-set / "how does X work"
question names the *intent*, not the files — so finding the complete set requires navigating complex
relationships, which a curated subsystem map accelerates. The wiki helps **most where the task is
hardest**, which is exactly the value proposition.

## How to apply

- Evaluate and optimize the wiki on **multi-hop / new-developer / concept (absent-identifier)** tasks;
  keep single-hop Locate only as a small control stratum.
- The read-prompt must **balance recall vs precision** — a "read the wiki, then enumerate the complete
  set" prompt over-fetched and *lost* to a plainer prompt. That recall/precision balance is the first
  thing the optimizer should tune.

## Verify
- docs/llm-wiki/optimizer/self-optimizer-design.md — section 11 (P2a outcome & learnings) records the run and the numbers
- plugins/llm-wiki-optimizer/harness — the eval harness (pr_items.py change-set generator, report.py file-level scoring) that produced them

## Related
- See [Retrieval is agentic-read-markdown — llm-wiki has no search engine](./retrieval-is-agentic-read-markdown.md) — why the wiki's value is navigation, not vector retrieval.
