# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Purpose

`public-skills` is David Allada's public Claude Code **marketplace**. The repo root is the
marketplace (`.claude-plugin/marketplace.json`); plugins live under `plugins/`.

The first and current plugin is **`llm-wiki`**: an OKF-native knowledge wiki for Claude Code.
It lets Claude author, read, and (later) maintain a persistent OKF knowledge bundle for a
project. **Phase 1 (MVP) is shipped** — init / capture / explore / query / conform, all
confirm-first, gated by a deterministic Doctor. See [docs/llm-wiki](./docs/llm-wiki/) for the
product plan, phasing, and the Phase 1 technical plan.

## Repository layout

```text
.claude-plugin/marketplace.json   # marketplace manifest
plugins/llm-wiki/                  # the plugin
  .claude-plugin/plugin.json       # plugin manifest (note: inside .claude-plugin/, not plugin root)
  commands/                        # /llm-wiki:{init,capture,explore,query,conform} (.md slash commands)
  skills/wiki/                     # the llm-wiki:wiki skill (SKILL.md + references/)
  scripts/                         # doctor.py, secret_scan.py, fixtures/ (the test corpus)
llm-wiki/                          # this repo's own OKF bundle (dogfood + living example)
docs/llm-wiki/                     # PRODUCT_PLAN, PHASE_PLAN, PHASE_1_TECH_PLAN, README (index)
source_docs/                       # OKF spec/blog + Claude Code plugin-system reference
```

## Commands (test / validate)

Python 3 **stdlib only** — no build, no dependencies, no package manager.

- **Test the Doctor** (the conformance proof corpus — run after any change to `doctor.py`,
  `secret_scan.py`, or the rules):
  ```bash
  bash plugins/llm-wiki/scripts/fixtures/run_fixtures.sh
  ```
  Expect `pass=10 fail=0 skip=1` (the skipped `F-BL` fixture is a documented Phase 4 seam).
- **Validate a bundle**:
  ```bash
  python3 plugins/llm-wiki/scripts/doctor.py <bundle-dir> --mode strict --format text
  ```

## Architecture & conventions

- **Doctor is the conformance authority.** `doctor.py` deterministically enforces OKF v0.1
  (rules R1/R2/R3a–c). The `wiki` skill only makes drafts *near*-conformant; if they disagree,
  the Doctor wins. Commands stage writes to a `/tmp` bundle mirror and run the Doctor in bundle
  mode *before* writing anything.
- **Confirm-first.** No command writes to a bundle without showing the exact content/diff and
  getting explicit approval. `explore`/`query` are read-only.
- **Report-only secret scan.** `secret_scan.py` surfaces credentials in the capture diff but
  never blocks in Phase 1 (it becomes a blocking PreToolUse hook in Phase 3).
- **Tests are fixtures.** Each `scripts/fixtures/<name>/` is a minimal bundle with one planted
  defect; `expected/<name>.json` is its contract. Add a fixture + expected pair for any new rule
  *before* implementing it (TDD).
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

## source_docs/

Reference material (not itself an OKF bundle):

- `okf_spec.md` — distilled OKF v0.1 rules (the Doctor enforces these).
- `okf_blog.md` — Google Cloud's OKF announcement (2026-06-12).
- `okf_repo.md` — links to the OKF spec / repo / reference implementations.
- `claude_code_plugin_system.md` — how Claude Code marketplaces/plugins/skills/commands/hooks/MCP compose.
