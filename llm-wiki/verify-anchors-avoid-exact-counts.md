---
type: convention
title: Verify anchors should not assert exact fixture counts — they churn on every addition
description: A ## Verify anchor that asserts an exact test/fixture count (e.g. "run_hooks.sh → pass=30") goes objectively stale every time a fixture is legitimately added, triggering a self-heal cycle per addition; anchor the invariant instead (fail=0, or a ≥ floor), reserving exact values for facts that should not drift.
tags:
  - convention
  - verification
  - wiki-authoring
timestamp: 2026-07-02
---

# Verify anchors should not assert exact fixture counts

Observed twice in one working session: `phase-3-autonomy-architecture.md` anchored the hook
fixture gate's exact count (`pass=29`), and each legitimate fixture addition (29→30→34) made the
anchor objectively diverge, dispatching a `wiki-verifier` self-heal whose only "fix" was bumping
the number. The anchor was verifying a moving target, not an invariant.

**Convention:** anchor the *invariant*, not the snapshot —

- prefer `fail=0` (the gate is green) or a floor (`pass ≥ 29`) over an exact `pass=N`;
- reserve exact-value anchors for facts whose change would itself be the signal worth catching
  (a constant like `ENTROPY_MIN_LEN = 20`, a schema string, a wired hook event list);
- growing corpora (fixtures, concepts, commands) are moving targets by design — an exact count
  there converts routine growth into verification churn.

The self-heal machinery makes this cheap but noisy: each churn is a background agent run and a
bundle write for zero knowledge gained.

## Verify

- This is an authoring convention; spot-check that `## Verify` anchors in this bundle asserting
  gate results use `fail=0`/floor forms rather than exact `pass=N` snapshots (grep `pass=` across
  the bundle's concept files).
