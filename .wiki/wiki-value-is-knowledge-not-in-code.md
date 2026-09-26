---
type: decision
title: Evaluate the wiki on knowledge the code can't tell you, with a weaker agent
description: Wiki-vs-ablated runs showed uplift only for a weaker agent, for runtime knowledge and the why, and for answer completeness; benchmark there, not on file-finding a strong agent already greps.
tags: [optimizer, evaluation, llm-wiki]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:39Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:39Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: docs/llm-wiki/optimizer/self-optimizer-design.md, title: section 11 P2a outcome and learnings}
  - {id: s2, resource: commit:e67cf1c, title: refine the value finding}
  - {id: s3, resource: commit:34b81f8, title: record the gotcha-recall corrective run}
---

# Evaluate the wiki on knowledge the code can't tell you, with a weaker agent

## Decision

When you measure, tune or promote llm-wiki (the `llm-wiki-optimizer` harness or any eval), use
tasks whose answer is **not in the code**: runtime root causes, the why behind a choice,
not-yet-committed fixes. Run them with a **weaker agent** and score **completeness**, meaning
caveats and key facts, not just the gist. File-finding and single-hop "where is X" tasks do not
measure the wiki.

## Why

The with-wiki vs wiki-ablated runs recorded in the optimizer design doc[^s1] split this way:

- **Agent strength.** On absent-identifier navigation, Sonnet gained +0.059 and Haiku gained
  +0.134, both with a CI that includes 0. A strong model finds the files by grepping. A weaker one is
  the agent the map rescues.
- **Knowledge in the code vs not.** In a gotcha-recall test over a real bundle for an
  infrastructure-as-code repo, the agent with no wiki still got 11/12 root causes, because those
  fixes were committed in the repo. The only miss was a runtime cross-service causal chain that no
  file encodes, and the wiki fixed it (12/12)[^s3].
- **Completeness.** Key facts surfaced went from 83% ablated to 100% with the wiki, even when the
  ablated answer was right in gist[^s2].

## Rejected alternatives

- Optimizing on grep-trivial navigation tasks. Uplift there was noise (about +0.03 single-hop) and
  would tune the read prompt toward nothing.

## Revisit when

A significance-powered run on the recommended setup (weaker agent, low-baseline, not-in-code items)
confirms or overturns it. Sample sizes so far were 20 or fewer per run, so none of these results
is significant yet.

## Verify

- `docs/llm-wiki/optimizer/self-optimizer-design.md` :: `P2a outcome & learnings`
- `docs/llm-wiki/optimizer/self-optimizer-design.md` :: `The corrective run`
