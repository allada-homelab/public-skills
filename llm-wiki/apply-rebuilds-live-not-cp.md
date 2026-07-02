---
type: decision
title: apply commits by re-building on live, not copying the mirror — concurrent-apply safety
description: bundle_ops apply's commit phase deliberately re-runs _build against the live bundle instead of cp-ing the validated /tmp mirror — copying the mirror's index.md over live would silently drop a concurrent apply's index entry, while re-building re-scans live and keeps both; don't "fix" this to copy-from-mirror.
tags:
  - architecture
  - durability
  - concurrency
  - gotcha
timestamp: 2026-07-02
---

# apply commits by re-building on live, not copying the mirror

Code reviewers repeatedly flag `bundle_ops.py apply` as defective because its commit phase re-runs
`_build` against the **live** bundle instead of copying the already-validated `/tmp` mirror — so the
committed bytes aren't guaranteed byte-identical to the validated ones, and docs once said it "lands
via `cp`". The mechanism is **deliberate**.

Each apply stages its mirror as a copy of live *at its own start*. Two applies can run concurrently
(a main-session `/llm-wiki:capture` plus a background `wiki-capturer`, or two background capturers).
If apply B (staged before A committed) copied its mirror's regenerated `index.md` over live, A's
freshly-added index entry would be silently dropped — A's concept file survives but vanishes from the
index. Re-running `_build` on live instead re-scans live's actual concept files at commit time, so
both entries survive.

The residual risk — live diverging between the gate and the commit — is covered by the post-commit
Doctor re-validation (which reports `error:post-commit` with a `git checkout` hint) and by
git-reversibility, the bundle's documented safety net.

**Do not "fix" this to copy-from-mirror**, even though that looks more atomic and makes the
validated-bytes guarantee literal. The concurrency behavior is the reason it is the way it is.

## Verify

- `plugins/llm-wiki/scripts/bundle_ops.py` — the apply commit phase (after the Doctor + secret gates)
  calls `_build(root_abs, ...)` against the live bundle; there is no `shutil.copy`/`cp` of mirror
  files into live.
