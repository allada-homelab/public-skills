---
type: Reference
title: OKF Doctor — strict-producer rule set
description: The conformance rules doctor.py enforces (R1/R2/R3a–c plus R4 link-health, R5 type-vocabulary, R6 provenance, and R7 bundle-shape), its strict/lenient modes, and exit codes.
tags:
  - doctor
  - conformance
  - okf
verified: 2026-07-17T00:00:00Z
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
- **R5 — Canonical `type` vocabulary (WARNING only).** A concept's non-empty `type` (R2 already passed)
  is checked case-insensitively against a fixed `CANONICAL_TYPES` set (e.g. `concept`, `decision`,
  `gotcha`, `reference`, `table`, `bigquery table`, …). OKF §3 only requires a non-empty `type`, so a
  drifted value is a curation nudge, not an error — R5 never changes the exit code.
- **R6 — Wiki-managed provenance (ERROR).** A `wiki_managed: true` concept must carry a `## Wiki
  provenance` JSON block, and any present provenance block must validate (complete, stable,
  objectively grounded).
- **R7 — Bundle shape (WARNING only, directory targets).** A bundle with zero concept files, or with
  concepts but no root `index.md`, gets a report-only warning — previously a moved/emptied bundle
  validated byte-identically to a healthy one (LW-1/LW-4 in the 2026-07-17 homelab bug report).
  Single-file targets skip R7; an auto-inited empty bundle legitimately warns until its first capture.

## Modes & output

- `--mode strict` (default) runs all rules; `--mode lenient` is a Phase 4 stub that exits `2`.
- `--format text` (human-readable) or `--format json` (deterministic, sorted findings).
- Exit codes: `0` = conformant (warnings allowed), `1` = one or more errors, `2` = operational error
  (bad path, a bare `index.md`, or `--mode lenient`). `-h`/`--help` prints usage and exits `0`.

The Doctor is validation-only — it never writes. The maintenance commands (`/llm-wiki:capture` /
`:prune` / `:reorganize`) make conformant changes deterministically via the shared `scripts/bundle_ops.py`
engine — including its consolidated **`apply`** gated-write subcommand (stage on a mirror → regenerate
index → append log → Doctor-gate → secret-scan → commit), which `capture` and the background
`wiki-capturer` agent both call. `reorganize` additionally diffs R4 before/after a move to guarantee it
introduces zero newly-broken links. Write gates key on ERROR only, so R4, R5, and R7 (all WARNING-only)
never block a write.

## Verify
- plugins/llm-wiki/scripts/doctor.py — contains R1/R2/R3/R4/R5/R6/R7 check implementations
- run: `grep -c "R7" plugins/llm-wiki/scripts/doctor.py` — expected: >= 4 (docstring + check_bundle_shape findings)
