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
writes is checked by the deterministic Doctor (`scripts/doctor.py`, strict-producer mode) at the staged
gate before the write lands. **If your draft and Doctor disagree, Doctor is right.** Never claim a bundle is
conformant on the basis of these instructions alone — run the Doctor.

## Reading is permissive

When *reading* a bundle (explore/query), be a tolerant consumer: missing optional fields, an unknown
`type`, unknown frontmatter keys, a missing `index.md`, or a broken link must **never** stop you from
reading.

## Reading is trust-but-verify

The wiki is a **somewhat-trusted summary** — curated, Doctor-gated, cross-linked: a good starting point,
not a guess, and **not** an unproven hypothesis to re-derive. The posture is **high prior, cheap check**:
lean on a finding and use it now, but before *acting* on a load-bearing one, cheaply confirm it still
holds against current state (usually the code) at the spot the concept points to. Trust the summary;
verify the spot — don't re-investigate from scratch (that defeats the point).

The mechanism (owned by `/llm-wiki:query`): a concept records a **`## Verify`** anchor (below) and a
`verified:` stamp; on read, a cheap freshness check (did the anchored file change since `verified:`?)
decides whether confirmation is even needed. When it is, confirmation runs in the **background on a
cheaper model** so the main loop is never blocked, and self-heals the concept only on an *objective*
(executable) divergence — never on a guess.

## Verify anchors — make a concept cheap to confirm

A code-grounded concept should carry a `## Verify` section: **where a reader confirms it in current
state**, so confirmation is a targeted glance, not a re-investigation.

- A **good** anchor is *checkable*: a resolvable `file:symbol`, or a runnable
  `run: <grep/one-liner> — expected: <result>`. **Never** prose-only ("see the code"); **never** a bare
  `file:line` (line numbers rot on the first edit above them → false verdicts).
- **Free-form text, NOT a markdown link.** Write `scripts/doctor.py:parse_frontmatter`, not a `[./…]`
  link — a real link into repo code would trip the Doctor's R4 link-health with false broken-link
  warnings. (Inter-*concept* links still use the `./` form in the body; anchors are not links.)
- **Repo-root-relative paths** (`scripts/doctor.py`), resolved against `${CLAUDE_PROJECT_DIR}`.
- Pair it with a **`verified:`** frontmatter stamp (ISO-8601) — when the anchor was last confirmed against
  current state; the freshness gate compares the anchored file's last change to it.
- If a fact is genuinely **not** code-checkable (a decision's rationale, an external dashboard), say so
  ("not code-verifiable; confirm via …") rather than writing a hollow anchor — these are confirm-exempt.

## Links use the relative `./` form

Cross-links are written as **relative** markdown links (`[Customers](./customers.md)`), in concepts,
`index.md` bullets, and `log.md` entries alike. Relative links are OKF-valid and resolve correctly when
the bundle is rendered on GitHub. See `references/linking.md`.

## Load references on demand

- Deciding whether/what to capture → skim `references/capture-triggers.md` (the high-value categories).
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
