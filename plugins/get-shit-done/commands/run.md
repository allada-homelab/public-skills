---
description: Get a complex or fan-out task done — decompose it, delegate each subtask to the cheapest capable model under an Opus/Fable orchestrator, research concurrently, fan out through a checked dynamic workflow, and adversarially verify (Opus) before reporting done.
argument-hint: "<what you want done>  [--dry-run]"
---

You are running `/get-shit-done:run`. This is the **orchestrator** entry for a complex or fan-out task.
Your job is to plan and delegate — not to do all the work yourself. Read the `get-shit-done` skill for
the full method (triage rubric, workflow cookbook, verification); this command is the driver.

`$ARGUMENTS` is the task. If it is empty, ask the user what they want done and stop.

**Precondition:** GSD fans out via the **Workflow** orchestration tool. If it is not available in this
session, say so plainly and stop — never silently no-op at the fan-out step.

Run these steps. This is **autonomous** — do not stop for plan/cost approval; stop only on a genuine
blocker (missing task, an unsafe/irreversible action that needs confirmation, or a hard tool failure).

1. **Orchestrator-model guard (one line).** State which model you are running as. GSD orchestration is
   tuned for **Opus** (or **Fable** if the user prefers). If you are *not* on Opus or Fable, warn:
   "⚠️ GSD orchestrates best on Opus — consider `/model opus`," then continue anyway. You (the
   orchestrator) stay on your current session model; only the *subagents* are tiered below.

2. **Load the method.** Read the `get-shit-done` skill and its `references/triage-rubric.md`. You will use
   the rubric to assign every subtask a model tier and effort.

3. **Plan & triage.** Decompose `$ARGUMENTS` into the smallest set of independently-executable,
   **file-disjoint** subtasks — the spine runs implementers concurrently in the *live tree* with no
   worktree isolation, so two units editing the same file would clobber each other (last write wins). For
   unavoidable overlap, use the cookbook's worktree-isolation variant instead of the spine.
   For each, assign per the rubric:
   - `tier`: `"sonnet"` for well-scoped, mechanical, or clearly-specified work; `"opus"` for open-ended,
     high-stakes, or hard-reasoning work. **Default is Opus** (subagents inherit your model), so you MUST
     set `"sonnet"` explicitly wherever it suffices — that is where the efficiency comes from.
   - `effort`: `"low"` for cheap mechanical steps, up to `"high"`/`"xhigh"` for the hardest reasoning.
   - `prompt`: a self-contained brief (inputs, exact deliverable, done-criteria) — a subagent is only as
     good as its brief.
   Also list 1–3 `researchTopics` the work depends on (APIs, library versions, best-practices) for the
   concurrent research pass.

4. **Fan out through the spine workflow.** Invoke the **Workflow** tool with the shipped, checked spine:
   - `scriptPath`: `${CLAUDE_PLUGIN_ROOT}/workflows/gsd.workflow.js` — if that variable is not expanded in
     your context, locate the file by globbing `**/get-shit-done/workflows/gsd.workflow.js`.
   - `args`: `{ "task": "<the full task>", "subtasks": [ …your triaged subtasks… ], "researchTopics": [ … ] }`.
   The spine runs Research (concurrent Sonnet, web + context7) ∥ Plan, then per-subtask Implement at the
   assigned tier, then an **adversarial Verify** pass — no barrier between implement and verify. If you are
   confident in your decomposition, pass your `subtasks`; to let the spine plan for you, pass just `task`
   and it triages internally. (Either way this runs the full spine — for genuinely small work, don't fan
   out at all: just do it inline.)
   - **`--dry-run`** in `$ARGUMENTS`: print your decomposition + per-subtask tiers + the `args` you *would*
     pass, and stop — do **not** invoke the workflow.

5. **Synthesize & report.** When the workflow returns, report what landed: confirmed units, any the verify
   pass flagged (with why), and the remaining steps that are the user's to run. Follow the repo's
   done-discipline — name what you confirmed vs. inferred, and never claim a green result you did not observe.

For tasks whose shape does not fit the spine (a migration sweep, a judge-panel design bake-off, a
loop-until-dry audit), see `references/workflow-cookbook.md` and author a custom workflow script instead.
