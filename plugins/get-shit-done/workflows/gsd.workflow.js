// get-shit-done — the spine workflow (static-checked by scripts/checks.sh; smoke-tested end-to-end).
//
// Shape: Research ∥ Plan  →  per-subtask Implement (at the assigned tier)  →  adversarial Verify.
// Implement→Verify is a pipeline (NO barrier): each subtask is verified the moment its
// implementation finishes, while other subtasks are still being built.
//
// Invoked by /get-shit-done:run via Workflow({ scriptPath, args }). args:
//   { task: string,
//     subtasks?: [{ title, prompt, tier: "sonnet"|"opus", effort? }],   // orchestrator's triage
//     researchTopics?: string[] }
// If subtasks are omitted, the spine plans them itself (Opus). Standalone-runnable with just { task }.
//
// SAFETY: implement subagents run in the live tree. Hand the spine FILE-DISJOINT subtasks, or the
// cookbook's worktree-isolation variant, when parallel units would edit the same files.

export const meta = {
  name: 'get-shit-done',
  description: 'Decompose a task, research it, implement each subtask at the cheapest capable tier, and adversarially verify before done.',
  phases: [
    { title: 'Research' },
    { title: 'Plan' },
    { title: 'Implement' },
    { title: 'Verify' },
  ],
}

const PLAN = {
  type: 'object',
  additionalProperties: false,
  properties: {
    subtasks: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          title: { type: 'string' },
          prompt: { type: 'string' },
          tier: { type: 'string', enum: ['sonnet', 'opus'] },
          effort: { type: 'string', enum: ['low', 'medium', 'high', 'xhigh', 'max'] },
        },
        required: ['title', 'prompt', 'tier'],
      },
    },
  },
  required: ['subtasks'],
}

const RESEARCH = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    sources: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary'],
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

// ---- inputs ----
const task = (args && args.task) || (typeof args === 'string' ? args : null)
if (!task) {
  log('gsd spine: no task in args.task — nothing to do')
  return { error: 'no task provided' }
}
const providedSubtasks =
  args && Array.isArray(args.subtasks) && args.subtasks.length ? args.subtasks : null
const researchTopics =
  args && Array.isArray(args.researchTopics) && args.researchTopics.length
    ? args.researchTopics
    : [task]

// ---- Research ∥ Plan (both run at once; plan may be pre-supplied by the orchestrator) ----
const [research, plan] = await parallel([
  () =>
    agent(
      `Gather the external knowledge the upcoming subtasks depend on. Use WebSearch/WebFetch (load via ToolSearch) for current best-practices; for any specific library/framework/tool, also use context7 docs tools (resolve-library-id then query-docs, load via ToolSearch). Be concrete and cite what you consulted.\n\nTask: ${task}\n\nTopics:\n${researchTopics.map((t, i) => `${i + 1}. ${t}`).join('\n')}\n\nReturn a compact summary an implementer can act on directly, plus sources.`,
      { label: 'research', phase: 'Research', model: 'sonnet', schema: RESEARCH },
    ),
  () =>
    providedSubtasks
      ? Promise.resolve({ subtasks: providedSubtasks })
      : agent(
          `Decompose this task into the smallest set of INDEPENDENTLY-executable subtasks (prefer file-disjoint). For each, give: a self-contained prompt (inputs, exact deliverable, done-criteria); a model tier — "sonnet" for well-scoped/mechanical/clearly-specified work, "opus" for open-ended/high-stakes/hard-reasoning work (default to "sonnet" wherever it plausibly suffices); and an effort level.\n\nTask: ${task}`,
          { label: 'plan', phase: 'Plan', model: 'opus', schema: PLAN },
        ),
])

const subtasks = plan && Array.isArray(plan.subtasks) ? plan.subtasks : []
if (!subtasks.length) {
  log('gsd spine: planning produced no subtasks')
  return { task, subtaskCount: 0, research, confirmed: [], flagged: [] }
}
const researchNote =
  research && research.summary
    ? `\n\n--- Research context (verify before relying on it) ---\n${research.summary}`
    : ''
log(
  `gsd spine: ${subtasks.length} subtasks — ` +
    `${subtasks.filter((s) => s.tier === 'sonnet').length} sonnet / ` +
    `${subtasks.filter((s) => s.tier !== 'sonnet').length} opus`,
)

// ---- Implement → adversarial Verify (pipeline: no barrier between the two) ----
const results = await pipeline(
  subtasks,
  (st) =>
    agent(`${st.prompt}${researchNote}`, {
      label: `impl:${st.title}`,
      phase: 'Implement',
      model: st.tier === 'sonnet' ? 'sonnet' : 'opus',
      effort: st.effort,
    }),
  (implOutput, st) =>
    parallel(
      [1, 2].map((n) => () =>
        agent(
          `You are an adversarial verifier — try to REFUTE that this subtask was done correctly and completely. Inspect the actual artifacts (read changed files, run any quick check available); do not take the implementer's word. Default to refuted=true if you cannot positively confirm.\n\nSubtask: ${st.title}\n${st.prompt}\n\nImplementer reported:\n${typeof implOutput === 'string' ? implOutput : JSON.stringify(implOutput)}`,
          // Verification always runs on Opus, regardless of the implement tier — the adversarial
          // gate is where correctness is decided, so it gets the strongest critic every time.
          { label: `verify:${st.title}#${n}`, phase: 'Verify', model: 'opus', schema: VERDICT },
        ),
      ),
    ).then((verdicts) => {
      const votes = verdicts.filter(Boolean)
      const refutes = votes.filter((v) => v.refuted)
      // Conservative gate: confirmed only if we got a verdict and NO verifier refuted.
      // Any refutation flags the unit for the orchestrator to adjudicate (the designed
      // escalation path) — research shows confident-but-wrong survives lenient majority
      // voting, so a lone skeptic is enough to withhold "confirmed". Single-pass, no
      // generator<->verifier refinement loop (avoids infinite loops / silent auto-approval).
      return {
        title: st.title,
        tier: st.tier,
        implOutput,
        verdicts: votes,
        confirmed: votes.length > 0 && refutes.length === 0,
        refutedBy: refutes.map((v) => v.reason),
      }
    }),
)

const done = results.filter(Boolean)
const confirmed = done.filter((r) => r.confirmed)
const flagged = done.filter((r) => !r.confirmed)
log(`gsd spine: ${confirmed.length} confirmed, ${flagged.length} flagged of ${done.length}`)
return { task, subtaskCount: subtasks.length, confirmed, flagged, research }
