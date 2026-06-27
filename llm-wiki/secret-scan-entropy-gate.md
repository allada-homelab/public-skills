---
type: Decision
title: Secret-scan entropy gate excludes path/URL separators
description: Why TOKEN_RE matches only contiguous opaque alnum runs — paths, URLs, and slugs were the dominant false-positive source that made the blocking secret guard deny legitimate wiki captures.
tags:
  - secrets
  - hooks
  - false-positives
verified: 2026-06-26T21:36:34Z
---
# Secret-scan entropy gate excludes path/URL separators

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

## Tradeoff

`+`, `=`, and `_` stay in the charset, so base64 and url-safe tokens are still caught. The
recall cost is narrow: a base64url secret split by `-` or `/` with no remaining 20-char
contiguous run could slip the entropy gate. That is acceptable because Stage 1's labeled
patterns catch the named high-value keys (AWS, GCP, Slack, GitHub, OpenAI/Anthropic, PEM,
connection strings) — the entropy gate is only a backstop.

## Verify
- plugins/llm-wiki/scripts/secret_scan.py — TOKEN_RE / entropy gate matching contiguous alnum runs, excluding path/URL separators
- run: `grep -n TOKEN_RE plugins/llm-wiki/scripts/secret_scan.py` — expected: a match showing TOKEN_RE definition and usage

## Related
- See [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the PreToolUse secret guard this scanner backs.
