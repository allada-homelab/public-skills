---
type: gotcha
title: ops fixture expect_err must not start with a dash — grep parses it as a flag
description: In scripts/ops_fixtures, an expected-stderr assertion whose text begins with "--" (e.g. asserting an error message that quotes a CLI flag like "--date must be...") breaks the harness — run_ops.sh matches with grep -qF and the leading dashes are parsed as grep options; start the asserted substring after the flag name instead.
tags:
  - gotcha
  - fixtures
  - testing
timestamp: 2026-07-02
---

# ops fixture expect_err must not start with a dash

The `ops_fixtures` harness asserts expected stderr with `grep -qF <expect_err> …`. If the asserted
text begins with `--` (natural when the error message being asserted quotes a CLI flag, e.g.
`--date must be an ISO date`), grep parses the leading dashes as its own option and the fixture
fails confusingly even though the message is correct.

**Fix/convention:** start the asserted substring *after* the flag name — assert
`date must be an ISO date`, not `--date must be an ISO date`. (Alternative harness-side fix would be
`grep -qF -- <pattern>`, but the convention keeps existing fixtures untouched.)

Hit while adding the `usage_apply_bad_date` / `usage_log_append_bad_date` fixtures: both failed on
the harness's grep, not on the behavior under test.

## Verify

- `plugins/llm-wiki/scripts/ops_fixtures/run_ops.sh` — the stderr assertion uses `grep -qF` with the
  fixture's expected-error text passed directly (no `--` end-of-options separator).
