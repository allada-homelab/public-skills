---
type: Decision
title: Secret-scan entropy gate excludes path/URL separators and camelCase identifiers
description: Why TOKEN_RE matches only contiguous opaque alnum runs and letters-only camelCase identifiers are exempt — paths, URLs, slugs, and Kubernetes-style field names were the false-positive sources that made the blocking secret guard deny legitimate wiki captures.
tags:
  - secrets
  - hooks
  - false-positives
verified: 2026-07-17T00:00:00Z
---
# Secret-scan entropy gate excludes path/URL separators and camelCase identifiers

`secret_scan.py` has two stages: labeled high-precision patterns (Stage 1) and an entropy
backstop (Stage 2) for unlabeled long tokens. The Stage-2 candidate regex is:

```
TOKEN_RE = [A-Za-z0-9+=_]{20,}
```

It deliberately **excludes the path/URL separators `/`, `-`, and `.`** so it only fires on a
*contiguous opaque alnum run*. A real unlabeled secret is one unbroken run; a markdown link
target (`planning/PRODUCT_PLAN.md`), a URL (`github.com/org/repo/blob/main`), or a hyphenated
slug (`future-ideas--backlog-not-committed`) is short word-pieces joined by separators, so each
piece falls under the 20-char length floor and never reaches the entropy check.

## Why

A knowledge wiki is dense with links, URLs, and slugs. The earlier charset included `/` and `-`,
so the gate treated whole paths/URLs as single high-entropy tokens — the dominant false-positive
source. Because the same scanner backs a **blocking** PreToolUse guard, those false positives
denied legitimate concept captures. Empirically: 14 corpus false-positives → 0 after the change,
with real planted secrets still denied and the hook suite at `pass=30`.

## camelCase identifier exemption (2026-07-17)

A second false-positive class survived the separator fix: long **letters-only camelCase
identifiers** (`maxNoOfPodsToEvictPerNode`, `nodeDrainPolicyBlockIfContainsLastReplica`) are
contiguous alnum runs and can clear the 4.0 bits/char entropy bar purely on case alternation —
and they are exactly the Kubernetes/API vocabulary a wiki must quote verbatim (LW-5 in the
2026-07-17 homelab bug report). Stage 2 therefore skips tokens matching `CAMELCASE_RE`
(lowercase head, capitalized humps, optional trailing acronym, **letters only** — any digit or
symbol disqualifies). A ≥20-char random secret is letters-only ~3% of the time and
camelCase-shaped essentially never, so the backstop is barely dented. A backtick/fence exemption
was rejected instead: backticked spans are where an agent would paste a discovered credential.

## Tradeoff

`+`, `=`, and `_` stay in the charset, so base64 and url-safe tokens are still caught. The
recall cost is narrow: a base64url secret split by `-` or `/` with no remaining 20-char
contiguous run could slip the entropy gate. That is acceptable because Stage 1's labeled
patterns catch the named high-value keys (AWS, GCP, Slack, GitHub, OpenAI/Anthropic, PEM,
connection strings) — the entropy gate is only a backstop.

## Verify
- plugins/llm-wiki/scripts/secret_scan.py — TOKEN_RE / entropy gate matching contiguous alnum runs, excluding path/URL separators; CAMELCASE_RE letters-only identifier exemption
- run: `grep -n "TOKEN_RE\|CAMELCASE_RE" plugins/llm-wiki/scripts/secret_scan.py` — expected: matches showing both definitions and the Stage-2 skip

## Related
- See [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the PreToolUse secret guard this scanner backs.
