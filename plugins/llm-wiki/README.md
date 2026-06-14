# llm-wiki

An OKF-native knowledge wiki for Claude Code. Claude builds and tends a persistent, portable
knowledge base for your project — a directory of markdown "concept" files in Google's
[Open Knowledge Format (OKF) v0.1](../../docs/llm-wiki/reference/okf_spec.md) — so each session starts
smarter than the last.

Everything the plugin writes is **OKF-conformant by construction** (a deterministic Doctor gates
every write) and **confirm-first** (you see the exact content/diff before it lands).

## Install

```text
/plugin marketplace add allada-homelab/public-skills
/plugin install llm-wiki@public-skills
/reload-plugins
```

## Commands

| Command | What it does |
|---|---|
| `/llm-wiki:init [path]` | Bootstrap a conformant bundle. Default location `./llm-wiki/`. |
| `/llm-wiki:capture [hint] [--bundle <path>]` | Turn a finding from the session into one conformant concept (dedupe-checked, Doctor-gated, secret-scanned). |
| `/llm-wiki:explore [subpath] [--bundle <path>]` | Navigate via `index.md` progressive disclosure (read-only). |
| `/llm-wiki:query <question> [--bundle <path>]` | Answer from the wiki with citations; flags a gap if unanswerable. |
| `/llm-wiki:conform [path] [--json]` | Run the Doctor and report conformance (read-only). |
| `/llm-wiki:refine [concept] [--bundle <path>]` | Edit an existing concept in place; indexes + log kept correct (Doctor-gated). |
| `/llm-wiki:prune [concept] [--bundle <path>]` | Remove a concept; dangling inbound links are *reported*, not rewritten. |
| `/llm-wiki:reorganize [what] [--bundle <path>]` | Move/rename concepts (incl. into subdirectories) with a zero-broken-links gate. |

The `llm-wiki:wiki` **skill** carries the OKF authoring/reading rules and auto-activates when you
talk about capturing to a wiki or knowledge base.

## How it works

- **Doctor (`scripts/doctor.py`)** — deterministic OKF v0.1 validator (rules R1/R2/R3a–c, plus
  report-only **R4** link-health). It is the conformance authority: the skill makes drafts
  *near*-conformant, the Doctor makes them *conformant*. Writes are staged to a temp bundle mirror and
  validated before anything is written.
- **Durability engine (`scripts/bundle_ops.py`)** — deterministic index regeneration, `log.md` appends,
  and link-preserving concept moves. The Phase 2 maintenance commands compose it instead of hand-editing
  indexes or links.
- **Secret scan (`scripts/secret_scan.py`)** — report-only credential scan surfaced in the capture
  diff (regex + entropy). It never blocks in Phase 1.
- **Confirm-first** — no bundle file is created or edited without explicit approval.

Default bundle location: `${CLAUDE_PROJECT_DIR}/llm-wiki`. Cross-links use relative `./` form so
they resolve on GitHub.

## Development

Python 3 **stdlib only**. Run both proof corpora:

```text
bash scripts/fixtures/run_fixtures.sh        # Doctor — expect pass=12 fail=0 skip=0
bash scripts/ops_fixtures/run_ops.sh         # bundle_ops golden — expect pass=12 fail=0
```

Status: **Phases 1 & 2 shipped.** Roadmap and design in
[../../docs/llm-wiki](../../docs/llm-wiki/).
