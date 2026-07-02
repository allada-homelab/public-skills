---
name: get-shit-done
description: >-
  Method for getting a complex or fan-out software task done by orchestrating
  subagents — decompose the task, delegate each subtask to the cheapest capable
  model (Sonnet for well-scoped work, Opus for hard reasoning) under an
  Opus/Fable orchestrator, run concurrent Sonnet research (web + context7), fan
  out through a checked dynamic workflow, and adversarially verify before done.
  Use when running /get-shit-done:run, or when the user wants to implement,
  build, migrate, or refactor something big enough to warrant decomposition and
  parallel fan-out. Explains the triage rubric (which tier per subtask), the
  workflow cookbook (authoring fan-out), and the verification gate.
---

# Get Shit Done — orchestrating complex & fan-out work

You are the **orchestrator** (Opus, or Fable if the user prefers). Your job is to *plan and delegate*,
then *integrate and verify* — not to do all the work inline. The heavy lifting fans out to subagents
tiered by complexity, over a checked spine workflow, with an always-on Opus adversarial verify pass.

Entry point: **`/get-shit-done:run <task>`** (`commands/run.md` drives the flow). This skill is the method
behind it.

## When to use this — and when not to

**Use it** when the task is big enough to earn decomposition: implementing a feature end-to-end, a
multi-file migration or refactor, a broad audit, anything with independent parallelizable pieces.

**Don't fan out** when the work is small, or has real **sequential dependencies**, or shares evolving
context across pieces (if fixing one thing might fix another, or two units would edit the same code). Most
coding tasks have fewer truly parallel pieces than they look. For those, a single focused agent (or just
doing it inline) beats fan-out — parallelizing a dependency chain produces wasted or broken work. Fan-out
pays on **breadth-first, low-dependency** work, and it costs ~15× a chat, so only fan out when the task's
value clears that.

## The loop

1. **Orchestrator-model guard.** State your model. GSD is tuned for Opus (or Fable). If you're on
   anything else, warn (`/model opus`) and continue — only subagents tier down; you stay put.
2. **Plan & triage.** Decompose the task into the smallest set of **independently-executable, file-disjoint**
   subtasks. Front-load ambiguity *now* (an ambiguous brief handed down-tier comes back wrong-shaped). For
   each subtask write a self-contained brief — inputs, exact deliverable, done-criteria, and an explicit
   *what NOT to touch* — then assign `tier` + `effort` per **`references/triage-rubric.md`**. Remember:
   **subagents inherit Opus** unless you set `"sonnet"` explicitly — that override is where the efficiency
   lives.
3. **Fan out through the spine.** Invoke the `Workflow` tool with `scriptPath` =
   `${CLAUDE_PLUGIN_ROOT}/workflows/gsd.workflow.js` and `args = { task, subtasks, researchTopics }`. The
   spine runs Research (concurrent Sonnet, web + context7) ∥ Plan, then per-subtask Implement at the
   assigned tier, then an Opus adversarial Verify pass — pipelined, no barrier between implement and verify.
4. **Integrate.** After the workflow returns, *your* job is integration, not more delegation: read every
   result, check whether any two units touched overlapping code, and run the **full** test/build suite once
   across the merged result — per-unit green checks don't prove a conflict-free whole.
5. **Report honestly.** Confirmed units vs. any the verify pass flagged (with why), plus the steps that are
   the user's to run. Name what you confirmed vs. inferred; never claim a green result you didn't observe.

This is **autonomous** — no plan/cost-approval gate. Stop only on a genuine blocker: a missing task, an
unsafe/irreversible action needing confirmation, or a hard tool failure. (`--dry-run` prints the plan
without spawning.)

## Delegate by complexity (the efficiency engine)

The validated pattern is a strong orchestrator over cheaper workers (Opus-lead + Sonnet-subagents beat
single-agent Opus by ~90% on Anthropic's eval). Route each subtask by three signals — **specifiability**,
**output verifiability**, and **task type** — and tune **effort before reaching for a bigger model**. Full
rubric with worked examples: **`references/triage-rubric.md`**. The one rule you can't skip: set
`tier: "sonnet"` *explicitly*, or it silently runs on Opus.

## Concurrent research (dogfood web + context7)

The spine's Research phase runs Sonnet agents that pull current docs and best-practices via WebSearch and
context7 (resolved through ToolSearch), concurrently with planning (it feeds Implement, so it's a
concurrent prerequisite, not fire-and-forget), and feeds a compact summary into the
implementer prompts. Treat those findings as **trust-but-verify** — an implementer confirms a load-bearing
claim against the real API before relying on it.

## Adversarial verification (always on)

Every implemented unit is checked by independent **Opus** verifiers before it counts as done (the gate is
where correctness is decided, so it always gets the strongest critic — even for Sonnet-tier work). Keep the critic
**independent**: it sees the requirements + the artifact, **never the implementer's reasoning trace**, and
inspects the real changes rather than trusting the self-report. **Any** refutation withholds "confirmed"
and flags the unit for you to adjudicate — a lone skeptic is enough, because confident-but-wrong output
survives lenient majority votes. It's single-pass-then-escalate: no generator↔verifier refinement loop
(which risks infinite back-and-forth or silent timeout-approval). For richer checks, route the verify
phase to a purpose-built reviewer (`pr-review-toolkit:code-reviewer`, `silent-failure-hunter`) — see the
cookbook.

## Utilize all tools

"Get it done" means composing the whole ecosystem, not reinventing it: `Explore` for codebase search,
`task-researcher`/context7/WebSearch for docs, the code-reviewer agents for verify, any session MCP tool
(reachable from workflow agents via ToolSearch), and existing skills (brainstorming, writing-plans) when
they fit. Inside a workflow, `agent(prompt, {agentType})` picks the right worker.

## Task shapes beyond the spine

For a migration sweep (parallel code mutation needs **git-worktree isolation** — parallel edits to one
tree clobber each other), a judge-panel design bake-off, or a loop-until-dry audit, author a custom
workflow script. Patterns, skeletons, and the Workflow authoring footguns are in
**`references/workflow-cookbook.md`**.

## Invocation modes

- **Explicit (default, always on):** `/get-shit-done:run <task>`.
- **Auto-trigger (shipped disabled):** an optional `UserPromptSubmit` hook nudges toward GSD when a prompt
  looks like fan-out work. It ships **off** — enable by copying `hooks/auto-trigger.example.json` to
  `hooks/hooks.json` and running `/reload-plugins`. See `scripts/gsd_autotrigger.py`.
