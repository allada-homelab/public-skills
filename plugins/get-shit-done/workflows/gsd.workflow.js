// get-shit-done — the spine workflow (static-checked by scripts/checks.sh; smoke-tested end-to-end).
//
// Shape: Research ∥ Plan  →  per-subtask Implement (at the assigned tier)  →  adversarial Verify.
// Implement→Verify is a pipeline (NO barrier): each subtask is verified the moment its
// implementation finishes, while other subtasks are still being built (serialized on a
// declared file collision).
//
// Invoked by /get-shit-done:run via Workflow({ scriptPath, args }). args:
//   { task: string,
//     subtasks?: [{ title, prompt, tier: "sonnet"|"opus", effort?, files? }],   // orchestrator's triage
//     researchTopics?: string[] }
// If subtasks are omitted, the spine plans them itself (Opus, which must declare each subtask's `files`).
// Standalone-runnable with just { task }. Returns { task, subtaskCount, research, confirmed, flagged },
// where each result carries { title, tier, implOutput, verdicts, confirmed, refutedBy, unverified }.
// `files` (declared or planned) drives collision detection: a shared file serializes implement→verify.
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
          files: { type: 'array', items: { type: 'string' } },
        },
        required: ['title', 'prompt', 'tier', 'files'],
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

const IMPL = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    changedFiles: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'changedFiles'],
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'refuted', 'couldnt_verify'] },
    reason: { type: 'string' },
  },
  required: ['verdict', 'reason'],
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
          `Decompose this task into the smallest set of INDEPENDENTLY-executable subtasks that are STRICTLY FILE-DISJOINT — no two subtasks may create or modify the same file. For each, give: a self-contained prompt (inputs, exact deliverable, done-criteria); a model tier — "sonnet" for well-scoped/mechanical/clearly-specified work, "opus" for open-ended/high-stakes/hard-reasoning work (default to "sonnet" wherever it plausibly suffices); an effort level; and \`files\` — the complete list of file paths that subtask will create or modify.\n\nTask: ${task}`,
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

// ---- stage helpers (shared by the concurrent pipeline and the sequential fallback) ----
// Implement one subtask at its assigned tier; returns { summary, changedFiles } or null if it died.
const runImplement = (st) =>
  agent(
    `${st.prompt}${researchNote}\n\nWhen done, return a one-paragraph summary of what you did plus the complete list of files you created or modified (empty array if none).`,
    {
      label: `impl:${st.title}`,
      phase: 'Implement',
      model: st.tier === 'sonnet' ? 'sonnet' : 'opus',
      effort: st.effort,
      schema: IMPL,
    },
  )

// Adversarial Verify: two live Opus verifiers with DISTINCT lenses must BOTH positively confirm.
// Any refutation, any 'couldnt_verify', or a dead verifier (only one live vote) withholds confirmed —
// a lone skeptic suffices, because confident-but-wrong survives lenient majority votes; and
// 'couldnt_verify' ("couldn't check") is not refutation but still can't count as confirmation.
// Single-pass-then-escalate: no generator<->verifier refinement loop (avoids infinite loops / silent
// auto-approval). Verifiers see requirements + the changed-file list only — NOT the implementer's
// narrative — for independence, and effort is pinned so the strongest-critic claim holds regardless
// of session effort.
async function runVerify(implOutput, st) {
  if (implOutput == null) {
    // Implementer died or was skipped — nothing to verify; withhold confirmation.
    return {
      title: st.title,
      tier: st.tier,
      implOutput: null,
      verdicts: [],
      confirmed: false,
      refutedBy: ['implementer returned no output'],
      unverified: [],
    }
  }
  const changed =
    Array.isArray(implOutput.changedFiles) && implOutput.changedFiles.length
      ? implOutput.changedFiles.map((f) => `- ${f}`).join('\n')
      : '(none reported)'
  const lenses = [
    'Your lens: COMPLETENESS vs the brief — check that every stated deliverable and done-criterion is actually present and correct in the changed files.',
    'Your lens: REGRESSIONS & side-effects — check the change did not break adjacent behavior, callers, or tests; look beyond the listed files.',
  ]
  const verdicts = await parallel(
    lenses.map((lens, i) => () =>
      agent(
        `You are an adversarial verifier — try to REFUTE that this subtask was done correctly and completely. Inspect the actual artifacts (read the changed files, check their callers/tests, run any quick check available); do NOT trust any claim — verify against the requirements and the real code.\n\n${lens}\n\nRequirements (the subtask):\n${st.title}\n${st.prompt}\n\nFiles the implementer reports it created/modified:\n${changed}${researchNote}\n\nReturn verdict 'refuted' ONLY with concrete evidence of a defect — state that evidence in reason. Return 'couldnt_verify' when you cannot positively confirm (missing access, ambiguous criteria); do NOT use 'refuted' for mere uncertainty. Return 'confirmed' only when you positively confirmed the deliverables are present and correct.`,
        { label: `verify:${st.title}#${i + 1}`, phase: 'Verify', model: 'opus', effort: 'high', schema: VERDICT },
      ),
    ),
  )
  const live = verdicts.filter(Boolean)
  const refutes = live.filter((v) => v.verdict === 'refuted')
  const unverified = live.filter((v) => v.verdict === 'couldnt_verify')
  const confirmed = live.length === 2 && refutes.length === 0 && unverified.length === 0
  return {
    title: st.title,
    tier: st.tier,
    implOutput,
    verdicts: live,
    confirmed,
    refutedBy: refutes.map((v) => v.reason),
    unverified: unverified.map((v) => v.reason),
  }
}

// Detect whether two subtasks declare the same file (unknown/absent files field = can't check → skip).
function findCollision(sts) {
  const owner = new Map()
  for (let i = 0; i < sts.length; i++) {
    if (!Array.isArray(sts[i].files)) continue
    for (const f of sts[i].files) {
      if (owner.has(f) && owner.get(f) !== i) {
        return { file: f, a: sts[owner.get(f)].title, b: sts[i].title }
      }
      owner.set(f, i)
    }
  }
  return null
}

// ---- budget guard: stop before spending on the fan-out if we're nearly out ----
if (budget.total && budget.remaining() < 30_000) {
  log('gsd spine: budget nearly exhausted — stopping before fan-out')
  return {
    task,
    subtaskCount: subtasks.length,
    error: 'budget exhausted before implement',
    research,
    confirmed: [],
    flagged: [],
  }
}

// ---- Implement → adversarial Verify ----
// File-disjoint subtasks pipeline (no barrier: each is verified the moment its implement finishes).
// A declared file collision means concurrent edits could clobber each other, so serialize instead.
const collision = findCollision(subtasks)
let results
if (collision) {
  log(
    `gsd spine: file collision on ${collision.file} (${collision.a} ↔ ${collision.b}) — ` +
      'running implement→verify SEQUENTIALLY',
  )
  results = []
  for (const st of subtasks) {
    const implOutput = await runImplement(st)
    results.push(await runVerify(implOutput, st))
  }
} else {
  results = await pipeline(
    subtasks,
    (st) => runImplement(st),
    (implOutput, st) => runVerify(implOutput, st),
  )
}

const done = results.filter(Boolean)
const confirmed = done.filter((r) => r.confirmed)
const flagged = done.filter((r) => !r.confirmed)
log(`gsd spine: ${confirmed.length} confirmed, ${flagged.length} flagged of ${done.length}`)
return { task, subtaskCount: subtasks.length, confirmed, flagged, research }
