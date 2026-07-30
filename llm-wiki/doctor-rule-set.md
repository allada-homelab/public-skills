---
type: Reference
title: OKF Doctor — strict-producer rule set
description: The conformance rules doctor.py enforces (R1/R2/R3a–c plus R4 link-health, R5 type-vocabulary, R6 provenance, R7 bundle-shape, R8 OKF v0.2 trust families, and R9 legacy-field migration), its strict/lenient modes, and exit codes.
tags:
  - doctor
  - conformance
  - okf
verified:
  - { by: llm-wiki/unknown, at: 2026-07-17T00:00:00Z }
  - { by: llm-wiki/claude-opus-5, at: 2026-07-30T02:56:20Z }
---
# OKF Doctor — strict-producer rule set

`scripts/doctor.py` validates an OKF v0.2 bundle deterministically. **Strict-producer mode** is the
pre-write gate for everything `/llm-wiki` authors; **lenient-consumer mode** is a Phase 4 stub.

## Rules

- **R1 — Parseable frontmatter.** Every concept opens with a `---` block that parses. The grammar covers
  scalars, `- item` lists, nested block mappings, block lists of mappings, and flow collections
  (`{ by, at }` / `[a, b]`) — the last three were added for the v0.2 trust families, which cannot be
  expressed without them. Tabs, an unterminated quote or flow collection, and a block that never closes
  are R1 errors.
- **R2 — Non-empty `type`.** A concept's frontmatter must contain a non-empty `type`. Evaluated only if
  R1 passed, so a single root cause is not double-reported.
- **R3a — Subdirectory `index.md`: zero frontmatter.** Any `---` block in a non-root `index.md` is an error.
- **R3b — Root `index.md`: only `okf_version`.** Frontmatter is optional; if present, the sole allowed
  key is `okf_version`, whose value must be the quoted string `"0.2"`. A superseded `"0.1"` is an R9
  warning (auto-migrated), not an R3b error; any other value is an R3b error. The emitted literal comes
  from `doctor.OKF_VERSION`, which `bundle_ops` imports rather than duplicating.
- **R3c — `log.md` structure.** ISO `YYYY-MM-DD` date headings, ordered newest-first, with bullets that
  begin with a bold `**Update**` / `**Creation**` / `**Initialization**` prefix.
- **R4 — Link health (WARNING only).** Internal markdown links (`/…` resolved from the bundle root, all
  others relative to the file) must resolve. Broken links are *tolerated* per spec §5, so R4 is a
  report-only WARNING that never changes the exit code — added in Phase 2. (The spec moved this rule to
  §6.1 in v0.2.)
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
- **R8 — OKF v0.2 trust/lifecycle/provenance families (ERROR when malformed).** `generated`, `verified`,
  `status`, `stale_after`, `sources`, and `usage_window` are each validated **only when present** —
  spec §11 forbids rejecting a concept for a *missing* optional family, so absence is never a finding.
  Checks: `generated.by` required and `generated.at` ISO-8601; `verified` a `{ by, at }` mapping or a
  non-empty list of them (a bare mapping is read as a one-element list, per §5.2); every identity field
  in the §7 actor convention (`<producer>/<version>`, `human:<id>`, `process:<id>`); `status` in
  `draft|stable|deprecated`; `stale_after` a plain `YYYY-MM-DD`; each `sources` entry carrying a
  `resource`, with unique `id`s. One report-only WARNING lives here too: a `[^label]` footnote that
  matches no `sources[].id`, since that join key is what per-claim attribution resolves through.
- **R9 — Legacy v0.1 fields (WARNING only).** `timestamp`, a bare scalar `verified:`, a body `Citations`
  section, and `okf_version: "0.1"` are the fields v0.2 superseded (§13.1). They warn rather than
  error — the spec permits consuming them — and `bundle_ops apply` rewrites them to v0.2 shape on the
  next write, so an installed v0.1 bundle keeps validating instead of being stranded. The one exception
  is the body `Citations` list: free-text citations don't map mechanically onto structured `sources`
  entries, so R9 keeps warning rather than letting the engine invent structure it can't recover.

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
introduces zero newly-broken links. Write gates key on ERROR only, so R4, R5, R7, and R9 (all
WARNING-only) never block a write — which is exactly what lets a legacy v0.1 bundle be migrated *by* a
write instead of having to be fixed before one.

## Verify
- plugins/llm-wiki/scripts/doctor.py — contains R1/R2/R3/R4/R5/R6/R7/R8/R9 check implementations
- run: `grep -c "R7" plugins/llm-wiki/scripts/doctor.py` — expected: >= 4 (docstring + check_bundle_shape findings)
- run: `grep -c '^OKF_VERSION = "0.2"' plugins/llm-wiki/scripts/doctor.py` — expected: `1` (the single
  source of truth `bundle_ops` imports rather than duplicating)
