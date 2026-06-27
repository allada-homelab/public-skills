# Repo ingestion — orchestration playbook

How `/llm-wiki:ingest` bootstraps a knowledge wiki from an existing repository: an **orchestrator**
(the command) fans out read-only **`wiki-explorer`** subagents (Sonnet), then synthesizes their
proposals into one conformant batch of concepts. This file is the methodology; the command body wires
it to the deterministic engine (`bundle_ops` + Doctor).

## Scope → work units & concept budget

`--scope` controls breadth. Defaults to **medium**.

| Scope | Intent | Work units (subagents) | Concept budget | What to cover |
|---|---|---|---|---|
| `min` | Minimal seed | 1–2 | ~2–4 | Architecture overview + the primary build/run runbook; maybe one core subsystem. |
| `medium` | Curated & thorough (default) | 3–8 | ~6–15 | Architecture, each major subsystem, build/test/deploy runbook, key schemas/APIs, notable decisions & gotchas. |
| `high` | Exhaustive | per significant subsystem/dir | ~40 (hard cap) | A concept per significant module/subsystem/domain. |

These are guides, not quotas — a tiny repo at `high` may yield few concepts; that's correct. **Never
truncate silently**: if the cap drops proposals, say so in the report and name what was cut.

## The orchestration loop

1. **Recon (orchestrator, cheap).** Read the repo's README, top-level layout, package manifests
   (`package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml` / …), CI configs, and any `docs/` or
   ADRs. Build a subsystem map. Also load the **existing** bundle concepts (slugs + titles +
   descriptions) so ingestion dedupes against what's already there.
2. **Partition into work units** sized by scope (table above). Each unit = a scope string + a per-unit
   concept budget. Keep units non-overlapping where possible; note expected overlaps for the merge.
3. **Fan out `wiki-explorer` subagents in parallel** (one per unit, `subagent_type: wiki-explorer`,
   model Sonnet). Give each: its scope, its budget, the repo root, and the output format. They are
   **read-only** and return concept proposals — they never write.
4. **Synthesize** (see below).
5. **Write the batch** through the Doctor-gated mirror protocol (the command body owns the exact
   commands), or — with `--dry-run` — print the plan and stop.
6. **Report** what landed (or would land), plus any R4/R5 warnings and any redactions.

## Synthesis rules

- **Dedupe.** Merge proposals with the same slug/title/topic — across subagents *and* against existing
  bundle concepts. Two thin proposals on one topic → one denser concept. Never create a concept whose
  topic an existing concept already covers (refine later instead).
- **Structure: flat-first.** Place concepts at the **bundle root** by default. Create a subdirectory
  **section** only for a real cluster — ~3+ sibling concepts on one sub-topic, or a distinct
  domain/subsystem with its own identity. A lone concept in a new folder is a **lonely folder** the
  Doctor flags as **R5** — avoid it. Prefer depth 1; rarely 2.
- **Assign final identity.** Give each concept its final `<dir>/<slug>.md` path. Compose frontmatter
  from the proposal: a non-empty `type`, `title`, `description`, `tags`, and a `timestamp`.
- **Write the Verify anchor.** For each concept with a non-empty `verify` array, compose a `## Verify`
  section from the array items and stamp `verified: <today>` in frontmatter. Omit both for an empty
  `verify` (confirm-exempt).
- **Resolve cross-links.** Map each proposed `links` slug to an actual concept's relative `./` path.
  Drop links to concepts that didn't make the cut (don't leave danglers); the Doctor's **R4** reports
  any that slip through (report-only).
- **Budget.** Keep the strongest concepts up to the scope cap; report anything dropped.

## Concept proposal schema (what subagents return)

```json
{
  "concepts": [
    {
      "type": "Subsystem",
      "title": "…", "slug": "kebab-case", "description": "one line",
      "tags": ["…"], "links": ["other-slug"], "sources": ["path"],
      "verify": ["file:symbol — what to confirm", "run: <one-liner> — expected: <result>"],
      "body_markdown": "concept body, no frontmatter, relative ./ links"
    }
  ],
  "notes": "overlaps / uncertainty / gaps"
}
```

## Safety (autonomous bulk write)

Ingestion is **autonomous** once invoked — no per-concept gate — so the floor matters more, not less:

- Every concept is **secret-scanned** in the mirror before it lands; a hit is **redacted** to a
  placeholder (never persist a credential), and the redaction is reported. (The cp-back bypasses the
  PreToolUse `secret_guard`, so this in-command scan is load-bearing — same as `/llm-wiki:capture`.)
- The whole batch is **Doctor-gated** in a `/tmp` mirror; nothing non-conformant lands. Doctor wins.
- The result is **one git-reversible diff**. Use `--dry-run` to preview the plan without writing, and
  `/llm-wiki:tend` to review afterward.
