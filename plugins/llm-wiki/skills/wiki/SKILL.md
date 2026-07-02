---
name: wiki
description: >-
  Build, maintain, and read a project knowledge wiki — a curated library of
  markdown notes the agent consults to start each session smarter. This skill
  should be used when the user wants to capture or save a finding, decision,
  runbook, schema, or metric into a wiki or knowledge base; or to read or
  query that wiki. The wiki follows the Open Knowledge Format
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
- **The wiki** — *consulted, reusable* knowledge to look **up** when relevant: findings, decisions
  (the "why"), runbooks, schemas, metrics, cross-cutting gotchas. Queryable, cross-linked,
  conformance-gated, and not auto-loaded in full — so it scales past always-in-context limits.

Rule of thumb: "how to behave in *this* directory" → a `CLAUDE.md` line; "a durable fact or decision
worth *retrieving later* across tasks" → a wiki concept. When a finding fits both, put the durable
record in the wiki and leave a one-line pointer in the local doc. Make the call explicitly and say why.

## The three hard rules (authoring constraints)

These are exactly what the Doctor enforces. Author to them:

- **R1 — Parseable frontmatter.** Every concept file opens with a `---` YAML frontmatter block that
  parses. Keep it simple: `key: value` scalars and simple `- item` lists.
- **R2 — Non-empty `type`.** Every concept's frontmatter has a `type` field with a non-empty value.
  `type` is any label the producer defines (e.g. `Reference`, `Runbook`, `BigQuery Table`).
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
should emerge from real clusters. Put a concept in a subdirectory only when there is a clear reason:

- ✅ it **joins an existing section** it clearly belongs to;
- ✅ it **forms/joins a cluster** — ~3+ sibling concepts on one sub-topic that should become a section
  (often paired with `/llm-wiki:reorganize` for the existing ones);
- ✅ it is a **distinct domain/subsystem** with its own identity and expected growth.

Avoid: a brand-new folder for a **single** concept, foldering by type with thin contents, and
speculative depth (prefer depth 1; rarely 2). When in doubt, root — and `reorganize` into sections later.

## Doctor is the authority — these rules guide, they do not verify

This skill makes a draft *near-conformant*; it does **not** make it conformant. Every file the plugin
writes is checked by the deterministic Doctor (`scripts/doctor.py`, strict-producer mode) at the staged
gate before the write lands. **If the draft and Doctor disagree, Doctor is right.** Never claim a bundle is
conformant on the basis of these instructions alone — run the Doctor.

## Reading is permissive

When *reading* a bundle (explore/query), be a tolerant consumer: missing optional fields, an unknown
`type`, unknown frontmatter keys, a missing `index.md`, or a broken link must **never** stop navigation.

## Reading is trust-but-verify

The wiki is a **somewhat-trusted summary** — curated, Doctor-gated, cross-linked: a good starting point,
not a guess, and **not** an unproven hypothesis to re-derive. The posture is **high prior, cheap check**:
lean on a finding and use it now, but before *acting* on a load-bearing one, cheaply confirm it still
holds against current state (usually the code) at the spot the concept points to. Trust the summary;
verify the spot — don't re-investigate from scratch (that defeats the point).

A concept records a **`## Verify`** anchor and a `verified:` stamp to make that spot-check cheap and
targeted; the freshness gate and self-heal are owned by `/llm-wiki:query`.

## The always-on loop (read first, persist in the background)

The wiki is always-on — there is no mode to enable. The main agent runs this loop itself:

- **Read first, without asking.** Before any non-trivial work, consult the wiki via `/llm-wiki:query`
  **proactively and without asking the user** — reading the wiki first is the default expectation, not
  an opt-in. Treat it as a first-class source alongside `CLAUDE.md` and READMEs.
- **The main agent owns judgment.** At the end of work *you* decide what (if anything) is durable and
  reusable, and you draft the concept per this skill. A subagent never makes that call.
- **Persist in the background.** Dispatch the **`wiki-capturer`** subagent (background) to write your
  drafted concept through the gated `bundle_ops apply` engine — don't write it to the bundle inline and
  don't block on it. It inherits nothing, so its brief must carry the whole payload: the bundle-relative
  concept path, the full drafted body bytes, the log kind (`Creation`|`Update`) with its linked log
  message, and the bundle root. It persists what you handed it; it does not re-curate.
- **Verify touched anchors.** Grep the bundle's `## Verify` blocks for the files you changed this turn;
  for each matching concept, dispatch one **`wiki-verifier`** subagent (background) — brief it with the
  concept path and the bundle root — to re-check it.

The Stop hook nudges this loop at end-of-turn, but it is the model's standing behavior, not the hook's.

## Verify anchors

Authoring rules — what makes a good anchor, the free-text-not-a-link constraint, repo-root-relative
paths, `verified:` stamping, and when to omit — are in `references/concept-template.md`.

## Links use the relative `./` form

Cross-links are written as **relative** markdown links (`[Customers](./customers.md)`), in concepts,
`index.md` bullets, and `log.md` entries alike. Relative links are OKF-valid and resolve correctly when
the bundle is rendered on GitHub. See `references/linking.md`.

## Load references on demand

- Deciding whether/what to capture → skim `references/capture-triggers.md` (the high-value categories).
- Authoring a concept → read `references/concept-template.md` (and `frontmatter.md` / `linking.md` as needed).
- Touching `index.md` / `log.md` → read `references/reserved-files.md`.
- Bulk-ingesting a repo → read `references/ingestion.md` (the `/llm-wiki:ingest` orchestration playbook).
- Reading/answering only → no authoring references needed.

Never paste the raw OKF spec into context — these notes plus the on-demand references are enough.

## Command map (orientation)

- `/llm-wiki:query` — answer a question grounded in concepts (citations + a gap flag), or browse from a point via `index.md` progressive disclosure. Read-only.
- `/llm-wiki:capture` — **upsert** a finding as one conformant concept: create it, or edit in place if it already exists (the core loop). No bundle is bootstrapped by hand — the first write auto-inits a conformant empty bundle.
- `/llm-wiki:prune` — remove a concept; dangling inbound links are *reported*, not rewritten.
- `/llm-wiki:reorganize` — move/rename concepts (incl. into subdirectories) with zero broken links.
- `/llm-wiki:tend` — emit a read-only curation digest (conformance, broken links, staleness, gaps) and propose maintenance.
- `/llm-wiki:ingest` — bootstrap a whole wiki from an existing repo (orchestrated multi-agent ingestion).

Each command owns its own arguments, allowed-tools, and Doctor wiring — this skill does not restate them.

## Maintenance is deterministic

`capture` / `prune` / `reorganize` never hand-edit `index.md`, `log.md`, or cross-links. Those are
regenerated by the shared `scripts/bundle_ops.py` engine: indexes are rebuilt from concept frontmatter
(root keeps only `okf_version`; subdir `index.md` gets zero frontmatter), `log.md` entries are appended
newest-first with the bold prefix, and a `move` rewrites every inbound link in **both** the `./` and `/`
forms. Decide *what* changes; the engine makes the change conformant and the Doctor gates
it (broken links are reported as `R4` warnings, never auto-deleted — broken links are tolerated per spec).
