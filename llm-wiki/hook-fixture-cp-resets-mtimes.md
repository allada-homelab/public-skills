---
type: gotcha
title: Hook fixtures can't test age-based behavior — the harness's plain `cp -r` resets mtimes
description: run_hooks.sh copies each fixture bundle with plain `cp -r` (no `-p`), so every copied file's mtime becomes test-run time — a branch gated on file age (e.g. the SessionStart sweep that removes session-scoped capture markers older than a day) can never be exercised by planting an "old" file in a fixture bundle. Fixtures can only cover the fresh-file path; the age branch stays code-review-only unless the harness gains an mtime-setting pre-step.
tags:
  - gotcha
  - fixtures
  - testing
  - hooks
---

# Hook fixtures can't test age-based behavior — the harness's plain `cp -r` resets mtimes

The hook golden harness copies each case's `bundle/` into a fresh tmp dir with plain `cp -r`
(no `-p`), so every copied file's mtime is the moment the test runs. Any hook branch gated on
file *age* therefore cannot be exercised by planting an old file in a fixture bundle — the file
arrives young.

Hit while fixturing the SessionStart stale-marker sweep (2026-07-04): the "session-scoped marker
older than a day is removed" branch is untestable this way; the corpus covers only the
young-marker-survives path (`session_start_sweeps_stale_markers`), plus the age-independent
legacy-marker removal. If an age branch ever needs a real fixture, the harness needs a pre-step
that sets mtimes (e.g. an optional per-case `touch -d` manifest) — don't switch the copy to
`cp -rp`, which would pin mtimes to git checkout time and silently change every existing case.

Sibling harness gotcha: [ops fixture expect_err must not start with a dash](./ops-fixture-expect-err-grep-flag-gotcha.md).

## Verify

- `plugins/llm-wiki/scripts/hook_fixtures/run_hooks.sh` — the bundle copy is plain `cp -r "$dir/bundle/." "$tmp/"` (no `-p`).
- `plugins/llm-wiki/scripts/hook_fixtures/session_start_sweeps_stale_markers/expected.json` — asserts the young session-scoped marker survives; no fixture asserts the >24h removal.
