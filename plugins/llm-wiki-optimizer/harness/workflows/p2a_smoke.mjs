export const meta = {
  name: 'p2a-smoke',
  description: 'P2a smoke: SUT subagent over the cell grid (with-wiki vs ablated, Sonnet vs Opus)',
  phases: [{ title: 'SUT grid' }],
}

const PRED_SCHEMA = {
  type: 'object',
  required: ['predicted'],
  properties: {
    predicted: {
      type: 'array', items: { type: 'string' },
      description: 'repo-root-relative file path(s) where the answer is defined, e.g. pkg/mod.py; [] if none',
    },
  },
}

const brief = (cand, question, repoPath, wiki, bundle) =>
  `${cand.prompt_text}\n\n` +
  `Answer ONE code-location question about the repository at ${repoPath}, read-only.\n` +
  `Use Grep and Read to ground every symbol in code you actually read.\n` +
  (wiki
    ? `A knowledge wiki for this repo is at ${bundle}; its index:\n${wiki}\n` +
      `Read the relevant concept files to orient FIRST, then confirm exact locations in code.\n`
    : '') +
  `QUESTION: ${question}\n` +
  `Return the file path(s) where the answer is defined, **relative to the repository root** ` +
  `(${repoPath}) — e.g. \`pkg/mod.py\`, NOT an absolute or clone-prefixed path. Empty list if none.`

// Ablated reference is candidate-independent (no wiki) — the cacheable baseline; comparing each
// candidate's with-wiki score against a FIXED no-wiki bar avoids the "win uplift by being a bad
// no-wiki prompt" gaming.
const BASELINE = { id: '__baseline__', prompt_text: 'Find the code locations that answer the question.' }

phase('SUT grid')

// Invoke via the Workflow tool with `args` = {items, candidates, wikiContext, wikiBundlePath, repoPath}.
// (Observed: `args` may not thread when a workflow is launched by `scriptPath`; if so, run an inline
// `script` with the data baked in. This guard fails loudly instead of with a cryptic `args.items` error.)
if (typeof args === 'undefined' || !args || !Array.isArray(args.items) || !Array.isArray(args.candidates))
  throw new Error('p2a_smoke.mjs requires args = {items, candidates, wikiContext, wikiBundlePath, repoPath}')

const cells = []
for (const item of args.items)
  for (const sut of ['sonnet', 'opus']) {
    cells.push({ item, cand: BASELINE, sut, cond: 'ablated' })        // one per item×tier
    for (const cand of args.candidates)                              // with-wiki: one per candidate
      cells.push({ item, cand, sut, cond: 'with_wiki' })
  }

const out = await parallel(cells.map((c) => () =>
  agent(
    brief(c.cand, c.item.question, args.repoPath,
          c.cond === 'with_wiki' ? args.wikiContext : '', args.wikiBundlePath),
    { label: `sut:${c.sut}:${c.cond}:${c.item.id}:${c.cand.id}`,
      model: c.sut, agentType: 'Explore', schema: PRED_SCHEMA },
  ).then((r) => ({
    item_id: c.item.id, candidate_id: c.cand.id, sut: c.sut, condition: c.cond,
    predicted: r ? r.predicted : [], ok: r !== null,
  }))
))

return { cells: out }
