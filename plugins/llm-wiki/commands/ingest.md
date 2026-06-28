---
description: Bootstrap a wiki from an existing repo (multi-agent).
argument-hint: "[repo-path] [--scope min|medium|high] [--bundle <path>] [--dry-run]"
allowed-tools: Task, Glob, Grep, Read, Write, Bash(python3:*), Bash(date:*), Bash(cp:*), Bash(rm:*), Bash(mkdir:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:ingest`. Populate an **existing** llm-wiki bundle from a whole repository by
**orchestrating** read-only `wiki-explorer` subagents (Sonnet) and synthesizing their proposals into one
conformant batch of concepts. Read the `wiki` skill for OKF format rules and load
`references/ingestion.md` for the full orchestration playbook (scope→budget, proposal schema, synthesis
rules) — this command is the wiring; that reference is the method.

This command is **autonomous once invoked**: it writes the whole batch without a per-concept gate. The
floor still holds — every concept is secret-scanned and the batch is **Doctor-gated** before anything
lands, and the result is **one git-reversible diff**. Use `--dry-run` to preview the plan without writing.

Arguments: `$ARGUMENTS` may carry a `[repo-path]` to ingest (default `${CLAUDE_PROJECT_DIR}`), a
`--scope min|medium|high` (default **medium**), a `--bundle <path>`, and `--dry-run`.

Steps:

1. **Resolve repo + bundle + flags.** Repo to ingest = `[repo-path]` if given, else `${CLAUDE_PROJECT_DIR}`.
   Bundle = `--bundle` if given; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki` if it holds a root
   `index.md` (`okf_version: "0.1"`); else walk up from the cwd. **No bundle found → use the default
   `${CLAUDE_PROJECT_DIR}/llm-wiki`** — the bundle is created automatically by the staging step (the
   `index` regen below writes a conformant root `index.md` with `okf_version: "0.1"`), so there is nothing
   to bootstrap by hand. Parse `--scope` (default `medium`) and `--dry-run`.

2. **Recon (orchestrator).** Survey the repo cheaply: README, top-level layout, package manifests, CI
   configs, any `docs/`/ADRs. Build a subsystem map. Also load the **existing** bundle concepts (Glob the
   bundle, read each concept's title/description) so ingestion **dedupes against what's already there**.

3. **Plan work units.** Partition the repo into non-overlapping exploration units sized by `--scope`
   (see the scope→budget table in `references/ingestion.md`): `min` → 1–2 units, `medium` → 3–8, `high`
   → one per significant subsystem (hard cap ~40 concepts total). Give each unit a scope string and a
   per-unit concept budget.

4. **Fan out subagents (parallel, Sonnet).** Dispatch one `wiki-explorer` per unit **in a single batch**
   (`subagent_type: wiki-explorer`), each briefed with: its scope, its concept budget, the repo root, and
   the proposal output format. They are read-only and return structured concept proposals — they write
   nothing. Collect every proposal block.

5. **Synthesize** (per `references/ingestion.md`): **dedupe** across subagents and against existing
   concepts; choose structure **flat-first** (a subdirectory section only for a real ~3+ cluster or a
   distinct domain — never a lonely folder); assign each concept its
   final `<dir>/<slug>.md` path and frontmatter (non-empty `type`, `title`, `description`, `tags`,
   `timestamp`); **resolve cross-links** to real `./` paths (drop danglers). Enforce the scope cap and
   **record anything dropped** (no silent truncation).
   **Verify anchors:** for each proposal carrying a non-empty `verify` array, append a `## Verify` section
   (its anchor lines, before `## Related`) and stamp `verified: <today>` in frontmatter — the explorer
   already confirmed it against the code it read. A proposal with an empty `verify` is confirm-exempt:
   no `## Verify`, no `verified:`. (See SKILL.md "Verify anchors": free-form text, not links.)

6. **`--dry-run` → stop here.** Print the plan: each concept as `path · type · title — one-line desc`,
   the proposed sections, the cross-link graph, and anything the cap dropped. Write nothing.

7. **Stage the batch in a mirror.** `mirror=$(mktemp -d)`; if the bundle already exists, seed the mirror
   with `cp -r "<bundle>/." "$mirror/"` (skip this `cp` when the bundle is absent — the `index` regen below
   writes a conformant root `index.md` into the mirror from scratch). Write every
   new concept into the mirror at its `<dir>/<slug>.md` (Write creates section dirs). **Secret-scan each
   before trusting it:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" "$mirror/<relpath>"
   --format json` — a **hit** is a non-zero `summary.findings` in the JSON (`secret_scan.py` always exits
   0, so never key the redaction off `$?`); on any hit, **redact** the offending value to `<REDACTED>` in
   the staged file (never persist a credential) and note it for the report. Then regenerate indexes and append **one** batched
   log entry (capture the date once — `today=$(date -u +%F)` — and reuse `$today` in step 9):
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Creation --message "Ingested <N> concepts from <repo> (scope <scope>): [<title>](./<relpath>), …" --date "$today"`

8. **Doctor gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format
   json`. Exit ≠ 0 → **fix the offending concept(s)** in the mirror and re-run `index` + the Doctor until
   it passes (the Doctor wins — never land non-conformant content). Surface any `R4` (dangling link)
   **WARNINGs**; they don't block (broken links are tolerated per OKF spec §5).

9. **Apply (autonomous).** Land *exactly the gated bytes*: for each staged concept, `mkdir -p` its target
   parent directory (this creates the bundle root and any new section dirs, since `cp` does not create
   parents), then `cp` it back to `<bundle>/<relpath>`. Then reproduce the deterministic bookkeeping on the real
   bundle — `bundle_ops.py index "<bundle>"` and the same `bundle_ops.py log-append … --date "$today"` —
   and run the Doctor on `<bundle>` to confirm **PASS**. If any write fails, report exactly what landed.
   Clean up only a real mirror (`rm -rf "$mirror"` — never an unset path).

10. **Report.** A summary table of every concept created (`path · type · title`), the sections formed,
    the scope used, any concepts the cap dropped, any `R4` dangling links, and any secrets **redacted**.
    Close with: review via `git diff -- "<bundle>"`, curate with `/llm-wiki:tend`, and note the whole
    ingest is one git-reversible commit.

Defer every conformance judgment to the Doctor. Keep concepts dense and flat-first; let real clusters —
not guesses — become sections (`/llm-wiki:reorganize` can section them later).
