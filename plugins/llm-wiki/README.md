# llm-wiki

An OKF-native knowledge wiki for Claude Code. Claude builds and tends a persistent, portable
knowledge base for your project — a directory of markdown "concept" files in Google's
[Open Knowledge Format (OKF) v0.1](../../docs/llm-wiki/reference/okf_spec.md) — so each session starts
smarter than the last.

Everything the plugin writes is **OKF-conformant by construction** (a deterministic Doctor gates
every write). Writes are **auto by default** — applied directly in an auto mode (the default); you see
the exact content/diff and approve it only in **`curated`** mode or when you explicitly ask.

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
| `/llm-wiki:ingest [repo] [--scope min\|medium\|high] [--dry-run]` | Bootstrap a whole wiki from an existing repo: an orchestrator fans out read-only Sonnet `wiki-explorer` subagents, then writes one Doctor-gated batch of concepts. |
| `/llm-wiki:capture [hint] [--bundle <path>]` | Turn a finding from the session into one conformant concept (dedupe-checked, Doctor-gated, secret-scanned). |
| `/llm-wiki:explore [subpath] [--bundle <path>]` | Navigate via `index.md` progressive disclosure (read-only). |
| `/llm-wiki:query <question> [--bundle <path>]` | Answer from the wiki with citations; flags a gap if unanswerable. |
| `/llm-wiki:conform [path] [--json]` | Run the Doctor and report conformance (read-only). |
| `/llm-wiki:refine [concept] [--bundle <path>]` | Edit an existing concept in place; indexes + log kept correct (Doctor-gated). |
| `/llm-wiki:prune [concept] [--bundle <path>]` | Remove a concept; dangling inbound links are *reported*, not rewritten. |
| `/llm-wiki:reorganize [what] [--bundle <path>]` | Move/rename concepts (incl. into subdirectories) with a zero-broken-links gate. |
| `/llm-wiki:tend [--bundle <path>]` | Read-only curation digest (conformance, broken links, staleness, gaps) proposing maintenance. |

The `llm-wiki:wiki` **skill** carries the OKF authoring/reading rules and auto-activates when you
talk about capturing to a wiki or knowledge base.

## How it works

- **Doctor (`scripts/doctor.py`)** — deterministic OKF v0.1 validator (rules R1/R2/R3a–c, plus
  report-only **R4** link-health and **R5** lonely-subdir). It is the conformance authority: the skill makes drafts
  *near*-conformant, the Doctor makes them *conformant*. Writes are staged to a temp bundle mirror and
  validated before anything is written.
- **Durability engine (`scripts/bundle_ops.py`)** — deterministic index regeneration, `log.md` appends,
  and link-preserving concept moves. The Phase 2 maintenance commands compose it instead of hand-editing
  indexes or links.
- **Secret scan (`scripts/secret_scan.py`)** — credential scan (regex + entropy). Report-only in the
  capture diff; in Phase 3 the same scanner backs a *blocking* PreToolUse hook. Honors
  `pragma: allowlist secret` and skips obvious placeholders so documentation examples don't false-positive.
- **Autonomy hooks (Phase 3, `hooks/hooks.json` + `scripts/`)** — six events: **SessionStart** preloads
  the root index + active-mode notice + an *N concepts · tags* summary; **UserPromptSubmit** is a
  once-per-session **consult** nudge (the read loop's forcing function, symmetric to capture); a
  **PreToolUse** floor (`secret_guard.py` denies credential writes, `doctor_guard.py` denies
  non-conformant concept writes); **PostToolUse** drops the `.llm-wiki/capture-pending` marker; **Stop**
  (`hook_stop.py`) is the end-of-turn forcing function — in an auto mode, *only on a turn that changed
  real code* (gated by that marker), it blocks the stop once so the model decides capture-or-stop;
  **SessionEnd** prints a digest pointing at `/tend`. Mode lives in
  `.claude/llm-wiki.local.md` (`mode.py`); **default is `proactive` (auto)**, made safe by that
  always-on floor. Curated (propose-only) and Max are opt-in.
- **Repo ingestion (`/llm-wiki:ingest` + `agents/wiki-explorer.md`)** — bootstraps a whole wiki from an
  existing repo: the command orchestrates read-only **Sonnet** `wiki-explorer` subagents that return
  structured concept proposals, then synthesizes and writes one **Doctor-gated, secret-scanned** batch
  (flat-first; `--scope min|medium|high`; `--dry-run` to preview). Autonomous once invoked, one
  git-reversible diff. Playbook in `skills/wiki/references/ingestion.md`.
- **Auto by default; confirm only on request** — in an auto mode (the default) the write commands apply
  directly with no prompt and no prose recap; they confirm-first only in `curated` mode or when you
  explicitly ask. Every write — autonomous or not — still passes a secret scan and the Doctor gate, and is
  logged + git-reversible (`ingest` is autonomous regardless of mode, with `--dry-run` to preview).

Default bundle location: `${CLAUDE_PROJECT_DIR}/llm-wiki`. Cross-links use relative `./` form so
they resolve on GitHub.

## Development

Python 3 **stdlib only**. Run both proof corpora:

```text
bash scripts/fixtures/run_fixtures.sh        # Doctor — expect pass=15 fail=0 skip=0
bash scripts/ops_fixtures/run_ops.sh         # bundle_ops golden — expect pass=13 fail=0
bash scripts/hook_fixtures/run_hooks.sh      # hooks (mode/session/guards/nudges/stop/digest) — expect pass=26 fail=0
```

Status: **Phases 1 & 2 shipped; Phase 3 autonomy core landed** (modes, SessionStart preload, PreToolUse
guards, UserPromptSubmit consult nudge, `/tend`; PostToolUse + auto-digest + Max deferred). Roadmap and design
in [../../docs/llm-wiki](../../docs/llm-wiki/).
