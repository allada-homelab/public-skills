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

The `llm-wiki:wiki` **skill** carries the OKF authoring/reading rules and auto-activates when you
talk about capturing to a wiki or knowledge base.

## How it works

- **Doctor (`scripts/doctor.py`)** — deterministic OKF v0.1 validator (rules R1/R2/R3a–c). It is
  the conformance authority: the skill makes drafts *near*-conformant, the Doctor makes them
  *conformant*. Writes are staged to a temp bundle mirror and validated before anything is written.
- **Secret scan (`scripts/secret_scan.py`)** — report-only credential scan surfaced in the capture
  diff (regex + entropy). It never blocks in Phase 1.
- **Confirm-first** — no bundle file is created or edited without explicit approval.

Default bundle location: `${CLAUDE_PROJECT_DIR}/llm-wiki`. Cross-links use relative `./` form so
they resolve on GitHub.

## Development

Python 3 **stdlib only**. Run the conformance proof corpus:

```text
bash scripts/fixtures/run_fixtures.sh        # expect pass=10 fail=0 skip=1
```

Status: **Phase 1 (MVP) shipped.** Roadmap and design in
[../../docs/llm-wiki](../../docs/llm-wiki/).
