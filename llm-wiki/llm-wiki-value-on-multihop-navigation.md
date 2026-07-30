---
type: Decision
title: Where llm-wiki's value concentrates — knowledge the code can't tell you
description: Optimizer experiments show the wiki's measurable value concentrates at the intersection of a weaker agent, knowledge not recoverable from the code (subtle runtime root causes and the why), and answer completeness — it pays off for what the code cannot tell you, not for file-finding or fixes already committed in the repo.
tags:
  - optimizer
  - evaluation
  - retrieval
verified: { by: llm-wiki/unknown, at: 2026-06-29 }
---
# Where llm-wiki's value concentrates — knowledge the code can't tell you

A series of optimizer experiments (with-wiki vs wiki-ablated, over real code) converged on a clear,
conditional answer to "does the wiki help?". The value is **real but concentrated**, at the
intersection of three conditions:

1. **A weaker agent.** Uplift scales inversely with SUT strength. On absent-identifier navigation
   questions, Sonnet gained ~+0.06 (noise, CI ∋ 0) but the weaker Haiku gained ~+0.13 — a strong model
   greps well enough that the wiki adds little; a weaker one is rescued by the map.
2. **Knowledge not recoverable from the code.** Single-hop "where is X defined" is grep-trivial
   (~+0.03). The wiki's edge appears on the *non-obvious*: in a gotcha-recall test over a real
   78-concept bundle, an agent with the repo but no wiki still got 11/12 root causes right — because
   the repo is infrastructure-as-**code** and the fixes are committed there. The one it got **wrong**
   (a ZooKeeper-fsync → ClickHouse-readonly causal chain) is *runtime* knowledge the code never
   encodes — and the wiki flipped it right. The wiki is redundant with the code for already-fixed,
   code-encoded gotchas; it is decisive for the *why* and for runtime behavior.
3. **Completeness.** Even when an ablated agent gets the gist, it misses caveats the wiki carries —
   in the gotcha test, with-wiki surfaced **100%** of the key facts vs **83%** ablated (durability
   gaps, a second alert path, "it's NOT the obvious suspect" steers).

## Why

What is in the code, a strong agent can rediscover by reading it. What the wiki uniquely holds is
what *isn't* in the code: a surprising root cause, a version-interaction trap, a decision and its
rejected alternative, the lesson learned from a running system. **llm-wiki pays off for what the code
can't tell you.**

## How to apply

- Evaluate and optimize the wiki on **knowledge-not-in-code** tasks (subtle root causes, the *why*,
  runtime behavior, not-yet-committed fixes) and on **weaker agents** — not on file-finding, where a
  strong agent + grep already win.
- Don't expect measurable uplift where a strong agent plus the codebase already hold the answer.

*(Caveats: experiment N's were small (≤20/run) and not yet statistically significant; the
infrastructure-as-code confound — committed fixes — likely *understates* the wiki's value for
uncommitted knowledge.)*

## Verify
- docs/llm-wiki/optimizer/self-optimizer-design.md — section 11 (P2a outcome & learnings) records every run and this synthesis

## Related
- See [Retrieval is agentic-read-markdown — llm-wiki has no search engine](./retrieval-is-agentic-read-markdown.md) — the wiki is read agentically; its value is recall of curated knowledge, not vector retrieval.
