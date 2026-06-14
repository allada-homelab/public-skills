---
type: Reference
title: OKF Doctor — strict-producer rule set
description: The conformance rules doctor.py enforces (R1/R2/R3a–c), plus its modes and exit codes.
tags:
  - doctor
  - conformance
  - okf
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

## Modes & output

- `--mode strict` (default) runs all rules; `--mode lenient` is a Phase 4 stub that exits `2`.
- `--format text` (human-readable) or `--format json` (deterministic, sorted findings).
- Exit codes: `0` = conformant (warnings allowed), `1` = one or more errors, `2` = operational error
  (bad path, a bare `index.md`, or `--mode lenient`).

Broken cross-links are not walked by the Doctor in Phase 1 (they are WARNING-only per the spec); the
`/llm-wiki:capture` command runs its own report-only link check instead.
