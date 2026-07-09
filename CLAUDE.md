# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Purpose

`public-skills` is David Allada's public Claude Code **marketplace**. The repo root is the
marketplace (`.claude-plugin/marketplace.json`); plugins live under `plugins/`.

The first and current plugin is **`llm-wiki`**: an OKF-native knowledge wiki for Claude Code.
It lets Claude author, read, and maintain a persistent OKF knowledge bundle for a project.
It is **zero-config and always-on auto**: once a bundle exists, autonomy is on — there are no modes to
set. Six commands — `query` (answer + browse), `capture` (upsert: create-or-edit), `prune`,
`reorganize`, `tend` (curation digest + conformance), and `ingest` (repo bootstrap) — compose the
deterministic `bundle_ops` engine. The main agent owns curation judgment; background **Sonnet**
subagents (`wiki-capturer` persists a drafted concept, `wiki-verifier` re-checks touched anchors) do the
mechanical work. Every write is gated by a deterministic Doctor (OKF v0.1) plus a secret scan, applied
autonomously and git-reversibly through the consolidated `bundle_ops apply` engine. See
[docs/llm-wiki](./docs/llm-wiki/) for the product plan, phasing, and the per-phase technical plans.

## Repository layout

```text
.claude-plugin/marketplace.json   # marketplace manifest
plugins/llm-wiki/                  # the plugin
  .claude-plugin/plugin.json       # plugin manifest (note: inside .claude-plugin/, not plugin root)
  commands/                        # /llm-wiki:{query,capture,prune,reorganize,tend,ingest}
  agents/                          # wiki-explorer.md (/ingest fan-out) + wiki-verifier.md (touched-anchor re-check) + wiki-capturer.md (background gated persist); all Sonnet
  skills/wiki/                     # the llm-wiki:wiki skill (SKILL.md + references/, incl. ingestion.md)
  hooks/hooks.json                 # hooks: SessionStart, PreToolUse, UserPromptSubmit, PostToolUse, Stop
  scripts/                         # doctor.py, secret_scan.py, bundle_ops.py;
                                   #   hooks: hook_session_start.py, secret_guard.py, doctor_guard.py,
                                   #          hook_user_prompt.py, hook_post_tool.py, hook_stop.py
llm-wiki/                          # this repo's own OKF bundle (dogfood + living example)
docs/llm-wiki/                     # design docs (README = index/hub, TRIAL_BRIEF = dogfooding)
  planning/                        # PRODUCT_PLAN (vision) + PHASE_PLAN (roadmap + primitive map)
  phases/                          # per-phase tech plans (phase-1/2/3-tech-plan.md)
  reference/                       # OKF spec/blog/repo + Claude Code plugin-system reference
```

## Commands (test / validate)

Python 3 **stdlib only** — no build, no dependencies, no package manager.

- **Drift gate** (cross-file consistency — run after touching a manifest description or a duplicated
  convention):
  ```bash
  bash scripts/drift_check.sh
  ```
  Cross-file consistency (manifests, duplicated conventions); expect `PASS`.
- **Validate a bundle**:
  ```bash
  python3 plugins/llm-wiki/scripts/doctor.py <bundle-dir> --mode strict --format text
  ```

## Architecture & conventions

- **Doctor is the conformance authority.** `doctor.py` deterministically enforces OKF v0.1
  (rules R1/R2/R3a–c, plus report-only **R4** link-health and **R5** type-vocabulary). The `wiki` skill only makes drafts
  *near*-conformant; if they disagree, the Doctor wins. Writes are staged to a `/tmp` bundle
  mirror and Doctor-gated in bundle mode *before* anything lands.
- **Maintenance is deterministic.** `bundle_ops.py` (index regeneration, `log.md` appends,
  link-preserving moves, guarded remove) is the engine the write commands compose instead of
  hand-editing indexes/links. Its **`apply`** subcommand is the consolidated gated write — auto-init an
  absent bundle → stage a `/tmp` mirror → regenerate index/log → Doctor-gate → secret-scan → commit,
  emitting a JSON status (`applied | blocked:doctor | blocked:secret | error:post-commit`); `capture` and the background
  `wiki-capturer` both call it. `reorganize` gates on an R4 pre/post diff (`after ⊆ before` → zero
  newly-broken links).
- **Always-auto; zero-config.** Once a bundle exists, autonomy is on — there are no modes. The write
  commands (`capture`/`prune`/`reorganize`) apply directly with no per-write prompt and no prose recap;
  the safety net is the in-command Doctor gate (blocking) and secret scan (a **hard abort** on a hit),
  plus git-reversibility. (The apply writes via plain file I/O — a staged `/tmp` mirror is gated, then the
  live bundle is re-built with `open()`, never `cp`ed from the mirror — so the PreToolUse guard floor
  backstops *direct* bundle Write/Edit, not the command path; a bundle write issued via Bash likewise
  bypasses the guards and is covered only by the apply gate and git-reversibility.) `query`/`tend` are
  read-only. `ingest` (bulk repo bootstrap)
  is autonomous once invoked: every concept is still secret-scanned and the whole batch is Doctor-gated
  before it lands, with `--dry-run` to preview and one git-reversible diff.
- **Secret scan.** `secret_scan.py` surfaces credentials (honoring `pragma: allowlist secret` and
  skipping obvious placeholders so documentation examples don't false-positive). It runs inside
  `bundle_ops apply` as a **hard abort** before any write lands, and the same scanner backs the
  *blocking* PreToolUse `secret_guard` hook.
- **Autonomy is hook-driven, with a guard floor.** `hooks/hooks.json` wires five events:
  SessionStart (preload root index + an *N concepts · tags* summary + a consult reminder; titles-only
  above a size threshold, and a one-time bootstrap pointer when no bundle exists), PreToolUse
  (`secret_guard.py` denies credential writes, `doctor_guard.py` denies non-conformant concept writes —
  scoped to bundle `Write|Edit|MultiEdit`), UserPromptSubmit (`hook_user_prompt.py` — a once-per-session
  *consult* nudge (session-marker-gated): the read loop's forcing function, symmetric to capture),
  PostToolUse (`hook_post_tool.py` — after a non-bundle code edit it drops the session-scoped
  `.llm-wiki/capture-pending-<session_id>` marker the Stop hook gates on and emits nothing itself — the
  capture prompt is the Stop hook's job; session scoping keeps a concurrent session or background
  process from arming another session's nudge, and SessionStart sweeps stale markers),
  and Stop (`hook_stop.py` — the end-of-turn forcing function: *only on a turn that changed real code*
  (gated by that marker), it blocks the stop once — `stop_hook_active`-guarded — so the model decides
  capture-or-stop at the non-disruptive moment, drafting + dispatching `wiki-capturer`/`wiki-verifier` in
  the background; silent on pure-chat turns). Autonomy is on whenever the bundle exists — no config. Hooks
  are deterministic command scripts (no model-call hooks); changes need `/reload-plugins`.
- **Default bundle location is `./llm-wiki/`** (`${CLAUDE_PROJECT_DIR}/llm-wiki`).
- **Cross-links use the relative `./` form** (resolves on GitHub; OKF-valid).

## Naming

- The plugin / command / skill is **`llm-wiki`** (skill `llm-wiki:wiki`). It was renamed from an
  earlier "okf-wiki".
- **"OKF" / "Open Knowledge Format"** is kept only for the underlying *format/spec* — it's the
  interop-bearing standard, not ours to rename.

## OKF in one paragraph

OKF is a vendor-neutral spec for curated knowledge as **a directory of markdown files with YAML
frontmatter**. Each file is one "concept" (table, dataset, metric, runbook, API, …) and the file
path is the concept's identity. The only required frontmatter field is `type`; conventional
optional fields are `title`, `description`, `resource`, `tags`, `timestamp`. Concepts cross-link
via ordinary markdown links, forming a graph richer than the directory tree. Two reserved
filenames: `index.md` (progressive disclosure) and `log.md` (chronological change history).
Producers and consumers are independent — no SDK, account, or platform required.

## docs/llm-wiki/reference/

Reference material that grounds this repo's work (not itself an OKF bundle):

- `okf_spec.md` — distilled OKF v0.1 rules (the Doctor enforces these).
- `okf_blog.md` — Google Cloud's OKF announcement (2026-06-12).
- `okf_repo.md` — links to the OKF spec / repo / reference implementations.
- `claude_code_plugin_system.md` — how Claude Code marketplaces/plugins/skills/commands/hooks/MCP compose.
