---
type: runbook
title: "llm-wiki gates: unittest is the real suite, drift_check is red at HEAD"
description: Gate llm-wiki changes on its unittest suite, which CLAUDE.md omits; drift_check.sh already fails 19 checks at HEAD, so compare its FAIL count before and after instead of expecting PASS.
tags: [testing, llm-wiki, drift-check, gates]
generated: {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z}
verified:
  - {by: okf-wiki/opus, at: 2026-09-26T15:01:38Z, commit: f6fe3111a376}
sources:
  - {id: s1, resource: https://github.com/allada-homelab/public-skills/pull/4, title: PR 4 test and drift-check counts}
  - {id: s2, resource: commit:1a3d963, title: coprocessor rewrite that added tests and changed breadcrumbs}
  - {id: s3, resource: commit:44d6f34, title: removal of the old fixture corpora}
  - {id: s4, resource: scripts/drift_check.sh, title: marketplace drift gate}
---

# llm-wiki gates: unittest is the real suite, drift_check is red at HEAD

## When

Before and after any change under `plugins/llm-wiki/`, or when CLAUDE.md's "Commands" section
sends you to `drift_check.sh` and it fails.

## Steps

1. Run the unit suite from the plugin dir (stdlib only, no install):
   `cd plugins/llm-wiki && python3 -m unittest discover -s tests`. CLAUDE.md does not mention it.
   The old Doctor/ops/hook fixture corpora were deleted in 44d6f34[^s3]; the current `tests/`
   directory arrived with the coprocessor rewrite in 1a3d963[^s2] and is now the real regression gate.
2. Run `bash scripts/drift_check.sh` from the repo root **before** your change and record the FAIL
   lines. At HEAD it exits 1 with 19 FAILs[^s1][^s4]: the plugin.json description no longer names
   the commands, the `wiki +1: <title>` / `wiki ~: <title>` / `wiki blocked (...)` breadcrumbs it
   greps for were replaced by the Stop hook's shorter breadcrumbs in 1a3d963, and several placement
   phrases left `capture.md` and `ingestion.md`.
3. Run it again after and diff the FAIL list. A new FAIL is yours; the pre-existing 19 are not.

## Check it worked

The unittest run ends in `OK` (120 tests at the time of writing). The drift gate's FAIL list after
your change is the same as, or a subset of, the list before. If you fixed the drift gate itself so it
prints `PASS`, this runbook is obsolete: deprecate it.

## Verify

- `scripts/drift_check.sh` :: `wiki +1: <title>`
- `plugins/llm-wiki/scripts/hook_stop.py` :: /wiki \+1: <title>/ => 0
- `plugins/llm-wiki/tests/test_hook_contracts.py` :: `import unittest`
