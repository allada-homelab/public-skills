---
type: Reference
title: OKF Doctor — strict-producer rule set
description: The conformance rules doctor.py enforces (R1/R2/R3a–c plus R4 link-health), its strict/lenient modes, and exit codes.
tags:
  - doctor
  - conformance
  - okf
verified: 2026-06-28T05:51:41Z
---
# OKF Doctor — strict-producer rule set

`scripts/doctor.py` validates an OKF v0.1 bundle deterministically. **Strict-producer mode** is the
pre-write gate for everything `/llm-wiki` authors; **lenient-consumer mode** is a Phase 4 stub.

## Rules

- **R1 — Parseable frontmatter.** Every concept opens with a `---` block that parses (scalars and simple
  `- item` lists). A missing or unparseable block is an R1 error.
- **R2 — Non-empty `type`.** A concept's frontmatter must contain a non-empty `type`. Evaluated only if
  R1 passed, so a single root cause is not double-reported.
- **R3a — Subdirectory `index.md`: zero frontmatter.** Any `---` block in a non-root `index.md` is an error.
- **R3b — Root `index.md`: only `okf_version`.** Frontmatter is optional; if present, the sole allowed
  key is `okf_version`, whose value must be `"0.1"`.
- **R3c — `log.md` structure.** ISO `YYYY-MM-DD` date headings, ordered newest-first, with bullets that
  begin with a bold `**Update**` / `**Creation**` / `**Initialization**` prefix.
- **R4 — Link health (WARNING only).** Internal markdown links (`/…` resolved from the bundle root, all
  others relative to the file) must resolve. Broken links are *tolerated* per spec §5, so R4 is a
  report-only WARNING that never changes the exit code — added in Phase 2.

## Modes & output

- `--mode strict` (default) runs all rules; `--mode lenient` is a Phase 4 stub that exits `2`.
- `--format text` (human-readable) or `--format json` (deterministic, sorted findings).
- Exit codes: `0` = conformant (warnings allowed), `1` = one or more errors, `2` = operational error
  (bad path, a bare `index.md`, or `--mode lenient`).

The Doctor is validation-only — it never writes. The maintenance commands (`/llm-wiki:capture` /
`:prune` / `:reorganize`) make conformant changes deterministically via the shared `scripts/bundle_ops.py`
engine — including its consolidated **`apply`** gated-write subcommand (stage on a mirror → regenerate
index → append log → Doctor-gate → secret-scan → commit), which `capture` and the background
`wiki-capturer` agent both call. `reorganize` additionally diffs R4 before/after a move to guarantee it
introduces zero newly-broken links.

## Verify
- plugins/llm-wiki/scripts/doctor.py — contains R1/R2/R3/R4 check implementations
- run: `bash plugins/llm-wiki/scripts/fixtures/run_fixtures.sh | grep -E "pass=|fail="` — expected: `pass=30 fail=0 skip=0`
