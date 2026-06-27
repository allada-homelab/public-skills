---
description: Tend the llm-wiki — emit a curation digest (conformance, broken links, staleness, gaps, orphans) and propose maintenance. Read-only.
argument-hint: "[--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(python3:*)
---

You are running `/llm-wiki:tend`. Produce a **reviewable curation digest** of the wiki and propose
maintenance — **read-only: never write, edit, move, or delete anything here.** All changes happen through
the `/llm-wiki:refine` / `:prune` / `:reorganize` commands (auto by default; confirm-first only in
`curated`), which the user runs after reviewing your digest. Use the `wiki` skill for format.

Arguments: `$ARGUMENTS` may carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up). None →
   "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Conformance.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>" --mode strict
   --format json`. Summarize: errors (R1/R2/R3*) and **R4 broken-link WARNINGs** (report-only). Broken
   links are *candidates to fix*, never auto-removed.
3. **Graph health.** From `index.md` listings and concept cross-links, surface **orphans** (concepts no
   index or concept links to), **near-duplicates** (very similar titles/slugs/`resource`s), and obvious
   **missing links** (concepts that clearly relate but aren't linked).
4. **Staleness.** Rank concepts by likely staleness using `timestamp` (if present), the newest `log.md`
   entry touching them, and any linked `resource`. If `<bundle>/.llm-wiki/consultations.json` exists,
   use it to prioritize: frequently-consulted concepts are worth keeping fresh; never-consulted + old
   concepts are prune/merge candidates. Treat a missing/corrupt counter file as empty — never fail on it.
   The counter is **not** maintained by `prune`/`reorganize`, so a key may be **orphaned** (point at a
   moved or removed concept) — ignore any count whose key no longer maps to an existing concept rather
   than reading it as "never consulted" signal.
5. **Gaps.** Note any topics the wiki plausibly should cover but doesn't (from its own structure). `GAP:`
   flags are **not persisted** — they exist only if `/llm-wiki:query` ran earlier in *this* session; list
   any you can still see in context, but don't imply the wiki remembers gaps across sessions.
6. **Digest.** Emit a single prioritized, **non-destructive** digest grouped by suggested action —
   `refine` (stale/incorrect), `prune` (orphaned/dead/superseded), `reorganize` (structure/links) — each
   item naming the concept and the one-line reason. End by offering to run the relevant command for any
   item the user picks. Propose nothing destructive without their go-ahead.
