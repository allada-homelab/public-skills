# llm-wiki

An OKF-native knowledge wiki for Claude Code. Claude builds and tends a persistent, portable
knowledge base for your project — a directory of markdown "concept" files in Google's
[Open Knowledge Format (OKF) v0.1](../../docs/llm-wiki/reference/okf_spec.md) — so each session starts
smarter than the last.

Everything the plugin writes is **OKF-conformant by construction** (a deterministic Doctor gates
every write). The plugin is **zero-config and always-on auto**: once a bundle exists, autonomy is on —
every write applies directly, gated by the Doctor and a secret scan, and is git-reversible. There are no
modes to set.

## Install

```text
/plugin marketplace add allada-homelab/public-skills
/plugin install llm-wiki@public-skills
/reload-plugins
```

## Commands

| Command | What it does |
|---|---|
| `/llm-wiki:query <question> [--bundle <path>]` | Answer a question from the wiki with citations (flags a gap if unanswerable), or browse from a point via `index.md` progressive disclosure. Read-only. |
| `/llm-wiki:capture [hint] [--into <subdir>] [--bundle <path>]` | Upsert a finding as one conformant concept — **create or edit** decided by file existence (dedupe-checked, Doctor-gated, secret-scanned). |
| `/llm-wiki:prune [concept] [--bundle <path>]` | Remove a concept; dangling inbound links are *reported*, not rewritten. |
| `/llm-wiki:reorganize [what] [--bundle <path>]` | Move/rename concepts (incl. into subdirectories) with a zero-broken-links gate. |
| `/llm-wiki:tend [--bundle <path>]` | Read-only curation digest (conformance, broken links, staleness, gaps) proposing maintenance. |
| `/llm-wiki:ingest [repo] [--scope min\|medium\|high] [--dry-run]` | Bootstrap a whole wiki from an existing repo: an orchestrator fans out read-only Sonnet `wiki-explorer` subagents, then writes one Doctor-gated batch of concepts. |

The `llm-wiki:wiki` **skill** carries the OKF authoring/reading rules and auto-activates when you
talk about capturing to a wiki or knowledge base.

## How it works

- **Doctor (`scripts/doctor.py`)** — deterministic OKF v0.1 validator (rules R1/R2/R3a–c, plus
  report-only **R4** link-health). It is the conformance authority: the skill makes drafts
  *near*-conformant, the Doctor makes them *conformant*. Writes are staged to a temp bundle mirror and
  validated before anything is written.
- **Durability engine (`scripts/bundle_ops.py`)** — deterministic index regeneration, `log.md` appends,
  and link-preserving concept moves. The write commands compose it instead of hand-editing indexes or
  links. Its **`apply`** subcommand is the consolidated gated write — auto-init an absent bundle → stage a
  mirror → regenerate index/log → Doctor-gate → secret-scan → commit, returning a JSON status; `capture`
  and the background `wiki-capturer` both call it.
- **Secret scan (`scripts/secret_scan.py`)** — credential scan (regex + entropy). Runs inside
  `bundle_ops apply` as a hard abort before any write lands, and the same scanner backs a *blocking*
  PreToolUse hook. Honors `pragma: allowlist secret` and skips obvious placeholders so documentation
  examples don't false-positive.
- **Autonomy hooks (`hooks/hooks.json` + `scripts/`)** — five events: **SessionStart** preloads
  the root index + an *N concepts · tags* summary + a consult reminder (titles-only above 40 concepts /
  16KB, with a `reorganize`/`tend` nudge; or a one-time startup pointer to `/llm-wiki:capture` when no
  bundle exists yet); **UserPromptSubmit** is a
  once-per-session **consult** nudge (the read loop's forcing function, symmetric to capture); a
  **PreToolUse** floor (`secret_guard.py` denies credential writes, `doctor_guard.py` denies
  non-conformant concept writes); **PostToolUse** drops the session-scoped
  `.llm-wiki/capture-pending-<session_id>` marker (so a concurrent session or background process in
  the same project can't arm another session's nudge; SessionStart sweeps stale ones); **Stop**
  (`hook_stop.py`) is the end-of-turn forcing function — *only on a turn that changed real code* (gated by
  that marker), it blocks the stop once so the model decides capture-or-stop, drafting + dispatching
  `wiki-capturer`/`wiki-verifier` in the background. Autonomy is on whenever the bundle exists — no config.
- **Repo ingestion (`/llm-wiki:ingest` + `agents/wiki-explorer.md`)** — bootstraps a whole wiki from an
  existing repo: the command orchestrates read-only **Sonnet** `wiki-explorer` subagents that return
  structured concept proposals, then synthesizes and writes one **Doctor-gated, secret-scanned** batch
  (flat-first; `--scope min|medium|high`; `--dry-run` to preview). Autonomous once invoked, one
  git-reversible diff. Playbook in `skills/wiki/references/ingestion.md`.
- **Always-auto; zero-config** — once a bundle exists the write commands apply directly with no prompt
  and no prose recap; there are no modes. Every write still passes a secret scan and the Doctor gate, and
  is logged + git-reversible (`ingest` adds a `--dry-run` to preview the batch first).

Default bundle location: `${CLAUDE_PROJECT_DIR}/llm-wiki`. Cross-links use relative `./` form so
they resolve on GitHub.

## Working in a team

The bundle is plain git — no server, no lock, no external state. **Concept files rarely conflict**: one
file is one concept, so parallel branches usually touch different files. The two regenerated artifacts,
**`index.md`** and **`log.md`**, *will* conflict on parallel branches, but resolution is trivial:

- **`index.md`** — take either side, then regenerate it from the merged concept files:
  `python3 <plugin>/scripts/bundle_ops.py index <bundle>`.
- **`log.md`** — union both sides' entries; the newest-first `## YYYY-MM-DD` date grouping merges cleanly.

## Development

Python 3 **stdlib only** — no build, no dependencies. Validate a bundle against OKF v0.1:

```text
python3 scripts/doctor.py <bundle-dir> --mode strict
```

Status: **zero-config always-auto** — 6 commands (`query`/`capture`/`prune`/`reorganize`/`tend`/`ingest`)
over the deterministic `bundle_ops` engine, with background `wiki-capturer`/`wiki-verifier` persist +
verify. Roadmap and design in [../../docs/llm-wiki](../../docs/llm-wiki/).
