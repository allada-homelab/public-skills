# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Purpose

`public-skills` is David Allada's public Claude Code **marketplace**. The repo root is the
marketplace (`.claude-plugin/marketplace.json`); plugins live under `plugins/`.

The first and current plugin is **`llm-wiki`**: an OKF-native knowledge wiki for Claude Code.
It lets Claude author, read, and maintain a persistent OKF knowledge bundle for a project.
**Phases 1 & 2 shipped; Phase 3 (autonomy) core landed** — Phase 1: init / capture / explore / query /
conform; Phase 2: refine / prune / reorganize over the deterministic `bundle_ops` engine + Doctor R4
link-health; Phase 3 core: autonomy mode (default `proactive`), SessionStart preload, a PreToolUse
secret/Doctor guard floor, UserPromptSubmit auto-capture, and the `/tend` digest (PostToolUse +
auto-digest + Max deferred). All user commands confirm-first, gated by a deterministic Doctor. See
[docs/llm-wiki](./docs/llm-wiki/) for the product plan, phasing, and the per-phase technical plans.

## Repository layout

```text
.claude-plugin/marketplace.json   # marketplace manifest
plugins/llm-wiki/                  # the plugin
  .claude-plugin/plugin.json       # plugin manifest (note: inside .claude-plugin/, not plugin root)
  commands/                        # /llm-wiki:{init,capture,explore,query,conform,refine,prune,reorganize,tend}
  skills/wiki/                     # the llm-wiki:wiki skill (SKILL.md + references/)
  hooks/hooks.json                 # Phase 3 hooks: SessionStart, PreToolUse, UserPromptSubmit, PostToolUse, Stop, SessionEnd
  scripts/                         # doctor.py, secret_scan.py, bundle_ops.py, mode.py;
                                   #   hooks: hook_session_start.py, secret_guard.py, doctor_guard.py,
                                   #          hook_user_prompt.py, hook_post_tool.py, hook_stop.py, hook_session_end.py
                                   #   fixtures/ (Doctor) + ops_fixtures/ (bundle_ops) + hook_fixtures/ (hooks)
llm-wiki/                          # this repo's own OKF bundle (dogfood + living example)
docs/llm-wiki/                     # design docs (README = index/hub, TRIAL_BRIEF = dogfooding)
  planning/                        # PRODUCT_PLAN (vision) + PHASE_PLAN (roadmap + primitive map)
  phases/                          # per-phase tech plans (phase-1/2/3-tech-plan.md)
  reference/                       # OKF spec/blog/repo + Claude Code plugin-system reference
```

## Commands (test / validate)

Python 3 **stdlib only** — no build, no dependencies, no package manager.

- **Test the Doctor** (the conformance proof corpus — run after any change to `doctor.py`,
  `secret_scan.py`, or the rules):
  ```bash
  bash plugins/llm-wiki/scripts/fixtures/run_fixtures.sh
  ```
  Expect `pass=12 fail=0 skip=0`.
- **Test the durability engine** (the `bundle_ops` golden corpus — run after any change to
  `bundle_ops.py`):
  ```bash
  bash plugins/llm-wiki/scripts/ops_fixtures/run_ops.sh
  ```
  Expect `pass=12 fail=0`.
- **Test the hooks** (the `hook_fixtures` corpus — run after any change to `mode.py` or a `hook_*` /
  `*_guard.py` script):
  ```bash
  bash plugins/llm-wiki/scripts/hook_fixtures/run_hooks.sh
  ```
  Expect `pass=25 fail=0`.
- **Validate a bundle**:
  ```bash
  python3 plugins/llm-wiki/scripts/doctor.py <bundle-dir> --mode strict --format text
  ```

## Architecture & conventions

- **Doctor is the conformance authority.** `doctor.py` deterministically enforces OKF v0.1
  (rules R1/R2/R3a–c, plus report-only **R4** link-health). The `wiki` skill only makes drafts
  *near*-conformant; if they disagree, the Doctor wins. Commands stage writes to a `/tmp` bundle
  mirror and run the Doctor in bundle mode *before* writing anything.
- **Maintenance is deterministic.** `bundle_ops.py` (index regeneration, `log.md` appends,
  link-preserving moves, guarded remove) is the engine the Phase 2 commands compose instead of
  hand-editing indexes/links. `reorganize` gates on an R4 pre/post diff (`after ⊆ before` → zero
  newly-broken links).
- **Confirm-first.** No command writes to a bundle without showing the exact content/diff and
  getting explicit approval. `explore`/`query`/`conform` are read-only.
- **Report-only secret scan.** `secret_scan.py` surfaces credentials in the capture diff but
  never blocks in Phase 1; in Phase 3 the same scanner backs a *blocking* PreToolUse hook.
- **Autonomy is hook-driven (Phase 3), with a guard floor.** `hooks/hooks.json` wires six events:
  SessionStart (preload root index + mode notice), PreToolUse (`secret_guard.py` denies credential
  writes, `doctor_guard.py` denies non-conformant concept writes — scoped to bundle
  `Write|Edit|MultiEdit`), UserPromptSubmit (`hook_user_prompt.py` — terse per-turn capture nudge),
  PostToolUse (`hook_post_tool.py` — nudge after a non-bundle code edit in an auto mode; mostly silent),
  Stop (`hook_stop.py` — the end-of-turn capture forcing function: in an auto mode it blocks the stop
  *once* per turn, `stop_hook_active`-guarded, so the model decides capture-or-stop at the
  non-disruptive moment), and SessionEnd (`hook_session_end.py` — a digest pointing at `/tend`). Mode (`mode.py`, from
  `.claude/llm-wiki.local.md`) defaults to **`proactive`** when absent; the floor is what makes that
  safe. Hooks are deterministic command scripts (no model-call hooks); changes need `/reload-plugins`.
- **Tests are fixtures.** `scripts/fixtures/<name>/` is a minimal bundle with a planted defect and an
  `expected/<name>.json` contract (Doctor); `scripts/ops_fixtures/<name>/` is an input→expected output
  tree for `bundle_ops`. Add a fixture *before* implementing any new rule or engine behavior (TDD).
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
