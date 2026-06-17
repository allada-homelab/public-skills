---
name: wiki
description: >-
  Build, maintain, and read a project knowledge wiki — a curated library of
  markdown notes the agent consults to start each session smarter. This skill
  should be used when the user wants to capture or save a finding, decision,
  runbook, schema, or metric into a wiki or knowledge base; or to initialize,
  explore, or query that wiki. The wiki follows the Open Knowledge Format
  (OKF v0.1); this skill explains its conformance and concept/frontmatter/linking
  rules so authored files are near-conformant before the deterministic Doctor
  gate runs. Also relevant when the user mentions llm-wiki, OKF, a concept doc,
  index.md, or log.md.
---

# Open Knowledge Format (OKF) v0.1 — authoring & reading

> ## ⚠️ NEVER put secrets in the wiki
> No API keys, access keys, auth tokens, passwords, SSH/PEM **private keys**, or connection
> strings containing credentials — **not even as an "example"**. The bundle is committed to git
> and reloaded every session, so a leaked secret is permanent and high-blast. Reference a secret
> by its **name and location** ("the `DEPLOY_TOKEN` env var", "the key in Vault at `…`"), never by
> value. A blocking secret guard backs this, but it is a backstop — do not rely on it; keep secrets
> out by hand.

## Mental model

An OKF bundle is a directory of markdown files. **One file = one concept** (a table, dataset,
metric, runbook, decision, API, gotcha, …). The **file path minus `.md` is the concept's identity** —
there is no separate ID field. Concepts cross-link with ordinary markdown links, forming a graph richer
than the directory tree. Two filenames are **reserved** and are never concepts: `index.md` (directory
listing / progressive disclosure) and `log.md` (chronological change history).

## Wiki vs. other docs — where knowledge goes

A repo usually already has `CLAUDE.md`, READMEs, and ADRs. Don't default everything to one or
guess silently — use the axis:

- **`CLAUDE.md` / in-tree docs** — *always-on, file-local* rules and specifics to follow while
  working in that directory (build/run commands, app conventions, local gotchas). Auto-loaded and
  colocated with the code they govern.
- **The wiki** — *consulted, reusable* knowledge you look **up** when relevant: findings, decisions
  (the "why"), runbooks, schemas, metrics, cross-cutting gotchas. Queryable, cross-linked,
  conformance-gated, and not auto-loaded in full — so it scales past what you'd keep always in context.

Rule of thumb: "how to behave in *this* directory" → a `CLAUDE.md` line; "a durable fact or decision
worth *retrieving later* across tasks" → a wiki concept. When a finding fits both, put the durable
record in the wiki and leave a one-line pointer in the local doc. Make the call explicitly and say why.

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

## When to nest (subdirectories)

Subdirectories are valid OKF (a subdir is a section with its own zero-frontmatter `index.md`), but
**default to the bundle root** — flat-first. Premature foldering guesses the taxonomy wrong; structure
should emerge from real clusters. Put a concept in a subdirectory only when you can name a reason:

- ✅ it **joins an existing section** it clearly belongs to;
- ✅ it **forms/joins a cluster** — ~3+ sibling concepts on one sub-topic that should become a section
  (often paired with `/llm-wiki:reorganize` for the existing ones);
- ✅ it is a **distinct domain/subsystem** with its own identity and expected growth.

Avoid: a brand-new folder for a **single** concept (a "lonely folder"), foldering by type with thin
contents, and speculative depth (prefer depth 1; rarely 2). The Doctor's **R5** warning flags a lonely
single-concept subdir as the backstop. When in doubt, root — and `reorganize` into sections later.

## Doctor is the authority — these rules guide, they do not verify

This skill makes your draft *near-conformant*; it does **not** make it conformant. Every file the plugin
writes is checked by the deterministic Doctor (`scripts/doctor.py`, strict-producer mode) in the
confirm-first diff. **If your draft and Doctor disagree, Doctor is right.** Never claim a bundle is
conformant on the basis of these instructions alone — run the Doctor.

## Reading is permissive

When *reading* a bundle (explore/query), be a tolerant consumer: missing optional fields, an unknown
`type`, unknown frontmatter keys, a missing `index.md`, or a broken link must **never** stop you from
reading.

## Links use the relative `./` form

Cross-links are written as **relative** markdown links (`[Customers](./customers.md)`), in concepts,
`index.md` bullets, and `log.md` entries alike. Relative links are OKF-valid and resolve correctly when
the bundle is rendered on GitHub. See `references/linking.md`.

## Load references on demand

- Authoring a concept → read `references/concept-template.md` (and `frontmatter.md` / `linking.md` as needed).
- Touching `index.md` / `log.md` → read `references/reserved-files.md`.
- Bulk-ingesting a repo → read `references/ingestion.md` (the `/llm-wiki:ingest` orchestration playbook).
- Reading/answering only → you need none of the authoring references.

Never paste the raw OKF spec into context — these notes plus the on-demand references are enough.

## Command map (orientation)

- `/llm-wiki:init` — bootstrap an empty conformant bundle (one-time).
- `/llm-wiki:ingest` — bootstrap a whole wiki from an existing repo (orchestrated multi-agent ingestion).
- `/llm-wiki:capture` — turn a finding into one conformant concept (the core loop).
- `/llm-wiki:explore` — navigate via `index.md` progressive disclosure.
- `/llm-wiki:query` — answer a question grounded in concepts, with citations and a gap flag.
- `/llm-wiki:conform` — run the Doctor and report (read-only).
- `/llm-wiki:refine` — edit an existing concept in place (indexes + log kept correct).
- `/llm-wiki:prune` — remove a concept; dangling inbound links are *reported*, not rewritten.
- `/llm-wiki:reorganize` — move/rename concepts (incl. into subdirectories) with zero broken links.
- `/llm-wiki:tend` — emit a read-only curation digest (conformance, broken links, staleness, gaps) and propose maintenance.

Each command owns its own arguments, allowed-tools, and Doctor wiring — this skill does not restate them.

## Maintenance is deterministic

`refine` / `prune` / `reorganize` never hand-edit `index.md`, `log.md`, or cross-links. Those are
regenerated by the shared `scripts/bundle_ops.py` engine: indexes are rebuilt from concept frontmatter
(root keeps only `okf_version`; subdir `index.md` gets zero frontmatter), `log.md` entries are appended
newest-first with the bold prefix, and a `move` rewrites every inbound link in **both** the `./` and `/`
forms. Your job is to decide *what* changes; the engine makes the change conformant and the Doctor gates
it (broken links are reported as `R4` warnings, never auto-deleted — broken links are tolerated per spec).
