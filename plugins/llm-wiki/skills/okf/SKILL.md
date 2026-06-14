---
name: okf
description: >-
  Knowledge of the Open Knowledge Format (OKF) v0.1 and the /llm-wiki workflow
  for building and reading an OKF knowledge bundle. This skill should be used
  when the user wants to capture a finding, schema, runbook, metric, or decision
  into a wiki or knowledge bundle; initialize, explore, or query an OKF bundle;
  or when the user mentions OKF, llm-wiki, a concept doc, index.md, or log.md.
  It explains OKF's conformance rules and concept/frontmatter/linking conventions
  so authored docs are near-conformant before the deterministic Doctor gate runs.
---

# Open Knowledge Format (OKF) v0.1 — authoring & reading

## Mental model

An OKF bundle is a directory of markdown files. **One file = one concept** (a table, dataset,
metric, runbook, decision, API, gotcha, …). The **file path minus `.md` is the concept's identity** —
there is no separate ID field. Concepts cross-link with ordinary markdown links, forming a graph richer
than the directory tree. Two filenames are **reserved** and are never concepts: `index.md` (directory
listing / progressive disclosure) and `log.md` (chronological change history).

## The three hard rules (authoring constraints)

These are exactly what the Doctor enforces. Author to them:

- **R1 — Parseable frontmatter.** Every concept file opens with a `---` YAML frontmatter block that
  parses. Keep it simple: `key: value` scalars and simple `- item` lists.
- **R2 — Non-empty `type`.** Every concept's frontmatter has a `type` field with a non-empty value.
  `type` can be any string you choose (e.g. `Reference`, `Runbook`, `BigQuery Table`).
- **R3 — Reserved-file structures.**
  - A **subdirectory** `index.md` has **zero frontmatter**.
  - The **root** `index.md` may carry **only** `okf_version: "0.1"` in frontmatter (nothing else), and
    that is the *only* place a version is declared.
  - `log.md` lists changes **newest-first**, with `## YYYY-MM-DD` (ISO-8601) date headings and bullets
    that begin with a bold prefix: `**Update**`, `**Creation**`, or `**Initialization**`.

See `references/` for the full field list, exact reserved-file shapes, and a copy-paste concept template.

## Doctor is the authority — these rules guide, they do not verify

This skill makes your draft *near-conformant*; it does **not** make it conformant. Every file the plugin
writes is checked by the deterministic Doctor (`scripts/doctor.py`, strict-producer mode) in the
confirm-first diff. **If your draft and Doctor disagree, Doctor is right.** Never claim a bundle is
conformant on the basis of these instructions alone — run the Doctor.

## Reading is permissive

When *reading* a bundle (explore/query), be a tolerant consumer: missing optional fields, an unknown
`type`, unknown frontmatter keys, a missing `index.md`, or a broken link must **never** stop you from
reading. (In Phase 1 this is a reading instruction to you; the enforced lenient-consumer Doctor mode
arrives in Phase 4.)

## Links use the relative `./` form

Cross-links are written as **relative** markdown links (`[Customers](./customers.md)`), in concepts,
`index.md` bullets, and `log.md` entries alike. Relative links are OKF-valid and resolve correctly when
the bundle is rendered on GitHub. See `references/linking.md`.

## Load references on demand

- Authoring a concept → read `references/concept-template.md` (and `frontmatter.md` / `linking.md` as needed).
- Touching `index.md` / `log.md` → read `references/reserved-files.md`.
- Reading/answering only → you need none of the authoring references.

Never paste the raw OKF spec into context — these notes plus the on-demand references are enough.

## Command map (orientation)

- `/llm-wiki:init` — bootstrap an empty conformant bundle (one-time).
- `/llm-wiki:capture` — turn a finding into one conformant concept (the core loop).
- `/llm-wiki:explore` — navigate via `index.md` progressive disclosure.
- `/llm-wiki:query` — answer a question grounded in concepts, with citations and a gap flag.
- `/llm-wiki:conform` — run the Doctor and report (read-only).

Each command owns its own arguments, allowed-tools, and Doctor wiring — this skill does not restate them.
