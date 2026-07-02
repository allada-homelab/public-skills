# get-shit-done

Get complex or fan-out work done. `/get-shit-done:run <task>` turns a big task into an orchestrated
fan-out: an **Opus/Fable orchestrator** decomposes it, delegates each subtask to the **cheapest capable
model** (Sonnet for well-scoped work, Opus for hard reasoning), runs **concurrent Sonnet research** (web +
context7), fans out through a **checked dynamic workflow**, and runs an **always-on adversarial verify**
pass before reporting done. Autonomous once invoked — no per-step approval; it stops only on a genuine
blocker.

## Requirements

- **Requires the `Workflow` orchestration tool** (multi-agent fan-out). Invoking `/get-shit-done:run` is
  itself the opt-in; if the tool isn't available in your session, the command says so and stops rather
  than silently no-op'ing.
- Runs best with **Opus** (or **Fable**) as your session model — the orchestrator inherits your session
  model; only subagents tier down. GSD warns if you're on a smaller model.
- Optional external reviewer/research agents (`pr-review-toolkit:*`, `task-researcher`, …) enrich the
  verify/research phases when installed, but aren't required — GSD falls back to the default worker.

## Usage

```
/get-shit-done:run implement rate limiting on the public API, with tests
/get-shit-done:run migrate all call sites from old_client() to new_client()
/get-shit-done:run --dry-run <task>     # print the decomposition + tiers, don't spawn
```

## What ships

| Path | What |
|---|---|
| `commands/run.md` | The `/get-shit-done:run` entry — plans, triages, and drives the spine. |
| `skills/get-shit-done/SKILL.md` | The method (the loop, when-not-to-fan-out, verification). |
| `skills/get-shit-done/references/triage-rubric.md` | Which model tier + effort per subtask. |
| `skills/get-shit-done/references/workflow-cookbook.md` | Authoring fan-out beyond the spine (migration/worktree, judge panel, loop-until-dry). |
| `workflows/gsd.workflow.js` | The spine (static-checked + smoke-tested): research ∥ plan → tiered implement → Opus adversarial verify. |
| `hooks/auto-trigger.example.json` + `scripts/gsd_autotrigger.py` | Optional, **disabled** auto-trigger nudge. |
| `scripts/checks.sh` | Static conformance gate (`bash …/checks.sh` → `PASS`). |

## Auto-trigger (optional, off by default)

GSD is explicit-only out of the box. To have it nudge you toward `/get-shit-done:run` when a prompt looks
like fan-out work, copy `hooks/auto-trigger.example.json` to `hooks/hooks.json` (drop the `_comment` key —
`hooks.json` is strict JSON) and run `/reload-plugins`. It only ever *suggests*; it never blocks or edits.

## Design notes

The tier rubric, fan-out patterns, and the adversarial-verify gate are grounded in current multi-agent
practice (Anthropic's Opus-lead + Sonnet-subagent research system, git-worktree isolation for parallel
code mutation, independent fresh-context verification). See the two reference files for sources.

- **"Checked", not "tested" end-to-end.** `scripts/checks.sh` is the committed static gate (manifests,
  spine JS, detector behavior, disabled-hook invariant). The spine was also smoke-tested end-to-end on a
  trivial task during development — but a behavioral fan-out fixture can't run offline (it needs live
  subagents), so it isn't part of the committed gate.
- **No `version` field, on purpose.** Like the other plugins in this marketplace, `plugin.json` omits
  `version` so Claude Code falls back to the git commit SHA — every commit auto-updates installed users
  during active development.
