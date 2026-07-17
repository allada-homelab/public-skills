---
description: Emit a read-only curation digest and propose maintenance.
argument-hint: "[--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(python3:*), Bash(git:*)
---

You are running `/llm-wiki:tend`. Produce a **reviewable curation digest** of the wiki and propose
maintenance — **read-only: never write, edit, move, or delete anything here.** All changes happen through
the `/llm-wiki:capture` (edit-in-place) / `:prune` / `:reorganize` commands, which the user runs after
reviewing your digest. Use the `wiki` skill for format.

Arguments: `$ARGUMENTS` may carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up). None →
   there is no wiki yet (one is created automatically on the first `/llm-wiki:capture`); say so and stop.
2. **Conformance.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>" --mode strict
   --format json`. Summarize: errors (R1/R2/R3*), **R4 broken-link WARNINGs**, and **R5 type-vocabulary
   WARNINGs** (concepts whose `type` is off SKILL.md's canonical vocabulary) — all report-only. Broken
   links are *candidates to fix*, never auto-removed; R5 off-vocabulary types are a *consistency* nudge
   (a `capture` edit-in-place toward a canonical token keeps grouping and this digest's analytics stable),
   never a block.
3. **Graph health.** From `index.md` listings and concept cross-links, surface **orphans** (concepts no
   index or concept links to), **near-duplicates** (very similar titles/slugs/`resource`s), and obvious
   **missing links** (concepts that clearly relate but aren't linked).
4. **Staleness.** Rank concepts by likely staleness using `timestamp` (if present), the newest `log.md`
   entry touching them, and any linked `resource`. Old concepts with no recent log activity are
   prune/merge candidates.
4a. **Anchor freshness sweep** (the proactive complement to the compiler/verifier's targeted checks).
   For each concept with a `## Verify` anchor + `verified:` stamp, run the cheap git gate against its
   anchored file(s): `git -C "${CLAUDE_PROJECT_DIR}" log --since="<verified>" -1 --format=%H --
   <anchor-file>`.
   **Non-empty (or the file no longer resolves)** → the anchored code changed since last
   verified → list as **needs re-verification** (a `capture` edit-in-place candidate; or point the user at
   `/llm-wiki:query <concept>`, whose read flow dispatches the verifier — `tend` is read-only and cannot
   dispatch one itself). Empty → fresh, skip. Also flag **anchor quality**: a *code-grounded* concept with no
   `## Verify`, or a weak one (prose-only "see the code", a bare `file:line`), is a curation gap to
   backfill — **skip** concepts explicitly marked not-code-verifiable (they're confirm-exempt). All
   read-only/`git`-only; never write here.
5. **Gaps.** Note any topics the wiki plausibly should cover but doesn't (from its own structure). `GAP:`
   flags are **not persisted** — they exist only if `/llm-wiki:query` ran earlier in *this* session; list
   any you can still see in context, but don't imply the wiki remembers gaps across sessions.
6. **Digest.** Emit a single prioritized, **non-destructive** digest grouped by suggested action —
   `capture` (edit-in-place: stale/incorrect, incl. **needs-re-verification** and weak/missing anchors
   from 4a), `prune` (orphaned/dead/superseded), `reorganize` (structure/links) — each item naming the concept and
   the one-line reason. End by offering to run the relevant command for any
   item the user picks. Propose nothing destructive without their go-ahead.
