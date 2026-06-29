# llm-wiki overnight self-optimizer — final design plan (Phase 1)

> **Status:** Phase-1 **final**, awaiting sign-off to begin Phase 2.
> **Scope this round:** Surface A (retrieval/comprehension) committed; Surface B (capture) a stretch goal.
> Incorporates the Phase-0 discovery + the deep-validation pass (corrections 1–13).
> **Models:** Claude-only (Opus + Sonnet) — external vLLM **de-scoped**; overnight compute is **metered, not free**.

---

## 0. The reframe that shapes the whole design

**llm-wiki has no retrieval engine.** A definitive grep across the plugin
(`embed|vector|faiss|rerank|top_k|topk|top-k|similarity|cosine|chunk`) returns only false positives.
"Retrieval" *is* an LLM agent running `grep`, reading the root `index.md`, following `./` links, and
reading whole concept files. The "index" is literally `index.md` — a bullet list, not a search index.

**Consequence:** the brief's assumed Surface-A knobs (embedding model, top-k, chunking, reranking)
**do not exist**. The real tunable surface is **~5 markdown prompts + the wiki's own structure/
description quality**, plus a few hardcoded constants. Both surfaces are *prompt + structure*
optimization, not RAG-hyperparameter search.

**The dividend:** because the system *is* "grep + read markdown," the wiki-ablated agent is the same
mechanism minus the curated concepts — so **uplift over the ablated agent isolates exactly what the
wiki adds**. That is our optimization signal (a proxy; see §3 for why it is *not* the north star).

---

## 1. The tunable surface (what the optimizer may edit)

The deterministic floor (Doctor / `bundle_ops` / secret scan) is **out of scope — never tuned**.

### Surface A — read path (committed)
| Component | File | What it governs |
|---|---|---|
| Traversal + grounding policy | `commands/query.md` (lines 32–61) | grep terms → read index → follow only on-topic links; answer only from concepts Read; emit `GAP:` when uncovered |
| Consult / trust-but-verify posture | `skills/wiki/SKILL.md` (lines 88–109) | read-first, "trust the summary, verify the spot", permissive navigation |
| Preload behavior | `hook_session_start.py` (lines 73–86) | full `index.md` injected on startup; SessionStart summary contents |
| `index.md` description quality | `bundle_ops index` from each concept's `description` | the only thing preloaded / shown in browse — bad descriptions = agent can't pick what to open |

### Surface B — capture path (stretch)
| Component | File | What it governs |
|---|---|---|
| Signal-vs-noise policy | `skills/wiki/references/capture-triggers.md` | the 7+2 durable-finding categories + the "don't invent a finding" noise floor — highest-leverage capture prompt |
| Upsert / dedup / placement | `commands/capture.md` (lines 33–65) | create-vs-update heuristic; flat-first structure; `## Verify` anchor + freshness |
| Bulk synthesis | `commands/ingest.md` + `references/ingestion.md` | dedup, densification, flat-first sectioning, no-silent-truncation |
| End-of-turn nudge | `hook_stop.py` `NUDGE` | the forcing-function restating durable categories |

**Also in-scope (secondary):** hardcoded constants — `secret_scan.py` `ENTROPY_MIN`/`PATTERNS`;
ingest scope budgets; the `~3+` cluster / nesting-depth thresholds.

**Engineering boundary (hard):** llm-wiki is **stdlib-only, zero deps** — its hooks run under bare
`python3` in the user's environment. The optimizer is a *separate* artifact with its own `uv`/
`pydantic` world; it drives llm-wiki **only** through stable CLI/JSON contracts (`okf-doctor/1`,
`okf-secret-scan/1`, the `bundle_ops apply` status line) via `subprocess`, and mutates prompt files
as **text**. It never imports llm-wiki code and never adds a dep llm-wiki's runtime would need.

---

## 2. Resolved decisions

| Decision | Choice |
|---|---|
| **Orchestration & runtime** | **Native Claude Code.** All LLM work is **subagents** (SUT / proposer / judge) dispatched from **dynamic Workflows** + **background subagents** — **no API key, SDK, or external endpoint** (auth + billing via the Claude Code session). The **Workflow runtime is the deterministic control loop + journaled `resumeFromRunId`**, replacing the standalone daemon (§5). The deterministic Python harness shrinks to LLM-free utilities (gold, scoring, store), driven by subagents via Bash. |
| **Search SUT** | **Sonnet (the cheap Claude tier) across all strata.** vLLM is de-scoped; the wide candidate search runs on Sonnet. **Compute is now metered, not free** — so search breadth is bounded by the token budget, which makes caching + successive-halving load-bearing rather than optional. |
| **Escalation / gate SUT** | **Capability-tiered, only at the narrowest end:** search **and top-K survivor selection both run on Sonnet**; only the **single winning config + the anchor** re-run on **Opus** (the complex multi-hop stratum) for final confirmation. This keeps Opus bounded and consistent with the budget. SUT model is **fixed per item** across candidates → paired comparison stays valid. **Load-bearing assumption (the riskiest in the plan):** candidate *rankings* transfer between the Sonnet search SUT and the Opus gate SUT. The wiki's value is plausibly model-dependent (a strong model may grep well enough that the wiki adds little), so this is **guarded in P2a** (§9) by measuring search↔gate ranking correlation; if low, "search cheap / gate expensive" is invalid and Opus must enter the search loop (bigger budget). |
| **Proposer (writes prompt edits)** | **Opus** — few calls/round, highest leverage; GEPA's reflective edits need a capable LM. |
| **Judge** | **Trimmed.** Cut from the Surface-A loop entirely (Explain is gated by *deterministic* evidence-coverage, so a judge can't move candidates across the gate). Reserved only for **Surface-B summarization faithfulness** + a **final-winner correctness audit** — there it is gated, reference-guided, CoT-rubric, a **different Claude tier** from the SUT (Sonnet judging Opus output, or vice versa), dual-order-flip→tie, length-controlled, human-calibrated. *Claude-only caveat: true cross-model-family judging isn't available, a documented limitation — bounded because the judge is already cut from the A loop and gate-only elsewhere.* |
| **Benchmark repos** | **Two Python repos** (§4): `allada-homelab/agents-scaffold` (private) = primary optimization target; `fastapi/fastapi` (public) = held-out transfer + contamination check. |
| **Surface scope** | **A primary, B stretch.** B depends on A's read path as its measurement instrument. |
| **Promotion** | **Auto-promote on significance — git-reversibly, generalization-gated** (§7): requires a significant win on the private held-out test **AND** no significant regression on the fastapi transfer set. Winner auto-written to the working tree + `ntfy`'d; **never pushed/merged** — you review the diff and merge. |
| **Baselines** | Wiki-ablated same-agent (primary contrast) + raw ripgrep (floor). **Vanilla vector = optional** floor, built only if cheap. |

### Config-driven defaults (nothing hardcoded — change at run time)
- `max_wallclock_hours: 8`; a **metered budget across both Claude tiers** — `max_sonnet_calls` (the
  wide search) **and** `max_opus_api_calls: 3000` (the Opus proposer across GEPA rounds + the
  single-winner final confirmation + calibration). **vLLM is de-scoped, so Sonnet volume now counts
  too** — there is no free tier. **These are estimates** — P2a measures real calls-per-task-loop *per
  tier* and recalibrates bottom-up (and gives a real $ figure) before the full run.
- Models (Claude-only, via **Claude Code subagents** — no API key/SDK): `search = Sonnet
  (claude-sonnet-4-6)`, `gate / proposer / complex = Opus (claude-opus-4-8)`. No endpoints to
  configure — auth is the Claude Code session.

---

## 3. Eval design

### Metric hierarchy: PRIMARY (north star) vs PROXY (what we optimize)
The thing we *optimize* is deliberately **not** the thing we ultimately *care about* — that gap is
why the circuit-breaker exists.

- **PRIMARY / north star (expensive, run rarely):** end-to-end **task success with-wiki vs
  without-wiki** — the anchor (below). This is what "the wiki helped" *means*.
- **PROXY / optimization signal (cheap, many per night):** **per-item uplift on Locate / Explain.**

### The proxy signal (Surface A), scored deterministically
Each task is a *small agentic read loop* — the SUT reads the wiki, greps, reads code, returns an
answer set — **scored programmatically** (the loop is light: no edits, no test runs). Aggregated
macro (per-question then mean), **stratified by hop count**:

- **Locate** — gold = code locations at **symbol identity** (AST-resolved, not line strings). Score =
  set **precision / recall / F1**, plus **recall@k / MRR** where ranked. *Utility-aware:* non-gold
  items carry **negative** weight (UDCG), so "return everything" cannot win recall.
- **Explain** — gold = the **evidence set**. Score = **evidence-set coverage** (deterministic;
  supporting-facts style). Coverage is both the score and the gate — **no LLM judge in this loop**.

### The naive baseline is the wiki-ablated SAME agent
**Uplift** = `score(SUT with wiki) − score(SUT, wiki ablated)` per item — *same model, same tools,
wiki removed from context, consult/preload prompts disabled*. This isolates **exactly what the wiki
adds to the same agent**. Raw **ripgrep** (and **optional** vanilla vector) are *secondary floor*
references. Objective is **gated on uplift > 0** — a wiki that adds nothing scores zero.

### Hard gates (the anti-reward-hacking core)
A per-item score is admissible only if it clears **all**: precision ≥ floor, answer tokens ≤ cap,
uplift > 0, and **empty-gold items answered with abstention**. Hard gates + negative-utility
distractors remove the recall/precision trade a soft penalty would leave open.

### Composition — Pareto truth, scalar decision
Source of truth = a **documented Pareto scheme** over (Locate, Explain, capture) quality. The
optimizer needs a total order → a **lexicographic / constrained scalar**: maximize the utility-aware
Locate+Explain score **subject to** the hard gates **and** "no axis regresses below frozen baseline."
Weights are never silently baked in (scalarization is itself a Goodhart trap).

### The anchor (concrete) + proxy↔anchor circuit-breaker (the master defense)
The anchor is a small held-out set of **SWE-style patch-and-test tasks** from `agents-scaffold`
post-cutoff PRs: give the SUT the issue, let it attempt a patch **with vs without the wiki**, score
by **whether the repo's tests pass** (deterministic, no judge). Every K rounds, track
**Spearman(proxy uplift, anchor test-pass delta)**. **If the correlation decays, optimization freezes
and alerts** — that decay *is* reward-hacking in progress. The single most important control.

### Surface B metric (stretch) — per-concept, penalty-weighted, mostly deterministic
Grounding rate · retrieval-utility (orphans = 0) · dedup ratio (MinHash; redundant = negative) ·
freshness (git + anchor-resolution; an unresolvable `file:line` is *provably* stale) · Doctor
conformance. The reserved rubric judge is a **gated bounded tiebreaker** for faithfulness only. Whole
metric **anchored to end-task uplift** so it can't drift into a paddable proxy. *(B also has a cheap
deterministic component that can screen candidates before the expensive KB-rebuild + read-path pass.)*

---

## 4. Benchmark repos, reference wiki & gold

### Two repos: private primary + public transfer/contamination control
Both **Python → one tree-sitter + pyright toolchain**, so the second repo costs pipeline runs, not a
second extractor. Verified 2026-06-28 via `gh`/local clone.

- **Primary optimization target — `allada-homelab/agents-scaffold` (private).** Zero contamination
  (private; created 2026-04-27, post-cutoff). **Rich gold supply: 500+ merged PRs in ~2 months**,
  many explicitly multi-file — the multi-hop chain supply the public repos lack. Clean signal *and*
  volume; the optimizer tunes here.
- **Held-out transfer + contamination check — `fastapi/fastapi` (public, MIT, 99.7k stars).** A
  *second frozen test set*, **not an optimization target** (~24 multi-file core commits since Feb is
  too thin). Roles: (a) does a config tuned on the private repo **transfer**; (b) quantify
  contamination two ways — the cross-repo uplift gap *and*, more cleanly, a **within-fastapi** measure
  (no-wiki performance on **pre-cutoff stable** vs **post-cutoff** code; a within-repo memorization
  signal that controls for repo-difficulty). Mitigations: post-cutoff PR gold only, Locate ≫ Explain,
  obfuscated-identifier stratum, canary items.
- **Dropped — sqlalchemy (logged):** 247k core LOC (180k even minus dialects) — over the 150k ceiling
  under every carve; the orm-only slice that fits *breaks* its engine↔orm chains; metaclass/visitor
  internals also make static call-graph gold unworkable. Out on size.
- **Public swap-in — `litestar` (~48k LOC, 8k stars):** better-supplied/lower-fame if we later want
  the public repo to carry optimization load.
- **Data-handling (private repo):** code is sent to Anthropic for **all** SUT/judge/proposer calls
  (Sonnet + Opus) — consistent with already running Claude Code over it. The harness sandboxes a
  clone, secret-scans, keeps gold/eval artifacts local and out of the committed `public-skills` repo.

### The frozen reference wiki (the Surface-A substrate)
Surface A optimizes the *read* prompt, meaningless without a wiki to read. Phase 2 builds and
**freezes a reference wiki over `agents-scaffold`**, held constant while the read prompt varies.

- **It is a *map*, not an answer key** — orienting knowledge (architecture, subsystems, gotchas,
  decisions); the gold is *specific locations the agent must still find*. Uplift = the map's
  navigational value. The wiki must **not** contain gold location sets — verified by (a) an automated
  check that no gold symbol's exact location appears verbatim in a concept, and (b) canary items.
- **Build:** run llm-wiki `ingest` (current prompts) → light polish to a *good* substrate. Its
  quality is a fixed confound for A and the **optimization target for B**. *(A↔B coupling: A is tuned
  against the current-prompts wiki; when B later changes the capture prompts the wiki shifts and A's
  optimum may move — handle as coordinate-descent/alternation if the coupling proves strong. Only
  bites once B is picked up.)*

### Gold extraction — deterministic, model-free (brief constraint #2)
- **Locate gold:** definitions via LSP `definition`, call sites via `references`/static call graph,
  types via `implementation`; symbol identity; hop-distance = stratum.
- **Explain gold — split by question type (construct validity):**
  - *"How was bug Y fixed / what changed for Z"* → **PR-diff is the correct evidence set** (the
    changed files/functions). Cleanest, fully model-free, naturally multi-hop.
  - *"How does mechanism X work"* → **call-graph closure** around the target (a fix PR touches only
    the *buggy subset*, not the whole mechanism — so PR-diff is wrong here). Closure = tool-derived.
- **No circularity:** an LLM (**distinct from the SUT** — phrasing and answering must not share a
  model) may **phrase** a question from a tool-derived fact; its answer is **discarded** and gold
  re-derived from tooling. **8-gram overlap exclusion** + **absent-/obfuscated-identifier** strata
  defeat grep-mimicry; a **lexical-overlap covariate** is recorded and regressed on to *prove*
  reasoning over greping. **Canary items** (gold injected into the KB) detect leakage.

### Real vs synthetic mix & splits (brief §7-Q2, constraint #4)
- **Real (backbone):** post-cutoff merged-PR-derived Locate + Explain. **Synthetic (volume):**
  call-graph-derived, to reach **≥50 items/stratum**. **Adversarial:** empty-gold + obfuscated.
- On the **private repo**: strict **train / dev / test**; train feeds reflective examples, dev drives
  selection, **test frozen** for the final gate. **fastapi is an additional frozen transfer set**,
  never seen by the optimizer. Gold kept **out of the KB** and **out of the optimizer's context** for
  both. **Pin tool versions** (tree-sitter grammar, pyright, git) so gold is reproducible; the test
  set is **frozen + content-hashed at P2b and never regenerated** (else cross-round comparisons are
  invalid).

### Item-quality validation (a garbage item bank invalidates everything)
"Ground truth first" cuts both ways — auto-generated *questions* can be unanswerable, ambiguous, or
trivially leaked. Two gates before an item enters the bank:
- **Auto-filter:** discard items where a **strong held-out model cannot recover the gold even with
  full code access** (unanswerable / bad question), or where the gold is **exact-string greppable**
  (too easy / leaked). The held-out validator is distinct from the SUT and the phrasing model.
- **Human audit:** a **~20-item sample the user eyeballs once** to confirm fairness and answerability,
  and to **calibrate the judge** (the only human label in the loop). This is the guard P2a's "uplift"
  number rests on.

---

## 5. Eval runtime, cost & unattended-run robustness

### Cost structure
The agentic eval at statistical scale (≥50/stratum × strata × ≥5 seeds × candidates × 2 conditions)
is the cost driver. Structure that keeps it inside an overnight **metered** budget:

- **Cheap-wide → expensive-narrow.** All search + top-K selection run on **Sonnet**; only the **single
  winner + anchor** escalate to **Opus**. Successive-halving kills weak candidates after a cheap
  1–2-seed screen; the final gate uses ≥5 seeds. *Sonnet is cheaper than Opus but not free — caching +
  halving are what keep the metered budget bounded now that there is no free tier.*
- **Cache invariants.** The **wiki-ablated baseline**, raw-ripgrep, and (optional) vector results are
  **constant across candidates** → computed once per item/seed and cached. The reference-wiki build is
  cached. Only the *with-wiki read* re-runs per candidate.
- **Sandbox.** Operate on copies of the KB + repo clone; never mutate anything live.

### Robustness — native Claude Code: deterministic Workflows + subagents (no daemon, no API key)
**The single most important robustness decision: the control loop is a deterministic *Workflow
script*, not an LLM deciding whether to continue.** All LLM work runs as Claude Code **subagents**
(SUT, proposer, judge), dispatched from **dynamic Workflows** and **background subagents** —
billed/authed through the Claude Code session, with **no `ANTHROPIC_API_KEY`, SDK, or external
endpoint**. This makes the SUT *maximally faithful* (a real Claude Code agent with native grep/read
tools — exactly how llm-wiki is used), while the **Workflow runtime, not a hand-rolled loop, owns
durability**. Relying on Claude Code's Stop-hook continuation to keep an *interactive* agent looping
all night is the fragile path we still avoid — but a *Workflow* is not that: its control flow is
deterministic code.

1. **Control flow is the Workflow script (deterministic JS).** `propose → evaluate the cell grid →
   select → repeat` is `agent()` / `parallel()` / `pipeline()` in a Workflow — not an LLM's choice.
   The subagents are workers the script calls; none can "stop the loop."
2. **Background execution + journaled resume (the daemon's replacement).** Workflows run in the
   **background** and **journal every `agent()` call**; a stopped or edited run relaunches with
   `resumeFromRunId` — completed cells return cached instantly, only unfinished cells re-run. Same
   *"compute only the empty cells"* property as a checkpoint store, native to the runtime.
3. **Fail open *toward progress*.** A subagent that dies returns `null` (`.filter(Boolean)`); the grid
   continues. Per-agent iteration/time caps live in the subagent brief; one bad cell never wedges the
   run. (Mirrors llm-wiki's "a guard must never wedge the session.")
4. **Tiered subagents.** SUT = Sonnet (search) / Opus (gate) via the agent `model`; proposer = Opus;
   judge = a different tier. The wide search runs as **background subagents** under the workflow's
   concurrency cap; only the single winner + anchor escalate to Opus.
5. **Durable cross-workflow state in SQLite.** The Workflow journal covers *intra-run* resume; the
   **SQLite store** holds *cross-workflow* durable state (gold, item bank, accumulated results) — so
   the 1000-agent/workflow cap is handled by **chaining sequential Workflows** (one per round/phase),
   the main agent reading results between and launching the next.
6. **Budget as a hard stop.** The Workflow `budget` gates `agent()` calls; the per-tier call/token
   caps (§2) are enforced in-script — breach → stop cleanly, already checkpointed. `ntfy` fires on
   milestone / stall / done / fatal.

**Honest robustness tradeoff (vs. the rejected standalone daemon).** Native Workflows are robust to
*agent-level* stalls — a deterministic script can't "decide to stop," and background + journaled
resume survive a hiccup — but they are **more coupled to the Claude Code session/host** than a systemd
daemon: if the whole session/host dies, the background work dies with it, and recovery means
relaunching + `resumeFromRunId` (or the journal-resume fallback — read `agent-*.jsonl` and hand-author
a continuation). The daemon survived host death but needed a raw API key, which is de-scoped.
**Overnight posture (decided).** Run the Claude Code session on an **always-on host** (the homelab
box); a **native scheduled wake** — `/loop` or a cron-style re-invocation (e.g. `CronCreate`) —
re-advances the pipeline and resumes any stalled Workflow from its journal (`resumeFromRunId`). No
external supervisor, no API key: background Workflows do the work between wakes, and host-death
recovery is relaunch + resume.

### Privacy containment (the private repo flows through the whole pipeline)
`agents-scaffold` code passes through prompts, logs, SQLite, and **`ntfy` payloads** (an *external*
notification service). Defenses: **secret-scan + redact everything outbound** — `ntfy` messages carry
status/metrics only, **never code snippets**; all eval data (clone, gold, logs, DB) lives in a
**gitignored local dir**; **no private code ever reaches the committed `public-skills` repo**. Reuse
llm-wiki's own `secret_scan.py` on any persisted/outbound artifact.

### Observability / reproducibility
Structured logging; one **SQLite** row per cell and per round (config hash, seed, dataset version,
all metrics, cost, timing, status). Reproducibility is **statistical** (CI over ≥5 seeds), not
bit-exact (the SUT is agentic) — pin temperature/prompt, record everything.

---

## 6. Optimizer

1. **Eval harness ships and self-validates first** (constraint #1) — proven on hand-crafted good/bad
   configs *and* **adversarial reward-hack configs** (a "return everything" prompt must score *worse*
   via the gates; a prompt with `GAP:`/abstention stripped must be caught) before any optimizer runs.
   The harness carries its own **unit tests** (scoring, gates, gold-extraction) per the brief's
   coverage bar; the self-validation + adversarial configs are its integration tests.
2. **Frozen baseline** — current prompts through the harness; mean ± CI on dev and test.
3. **Trivial random/grid optimizer first** — to prove fancier methods beat random.
4. **Bake-off: GEPA-style loop vs random.** The reflective propose-from-failures + Pareto-select loop
   is implemented **as a Workflow** — an **Opus proposer subagent** reads failing rows + the current
   prompt body and returns an edited prompt (frontmatter immutable); Pareto/selection live in the
   script — **adopted only if it beats random** on dev. *(The standalone `gepa` Python library expects
   an API-callable LM, which is de-scoped, so we reimplement its algorithm natively rather than adopt
   the library — the research already noted "borrow the ideas" ≡ reimplement GEPA.)* The
   precision/recall delta + failure rationale are the reflective "textual gradient."
5. **Prompt-edit structural validator** — every proposed prompt is linted for required elements (e.g.
   the `GAP:`/abstention instruction, grounding rule) **before** evaluation, so the optimizer cannot
   game the metric by *deleting a constraint*.
6. **Ship-gate (we build this — no framework provides it):** paired **Wilcoxon signed-rank** for
   win/no-win, **paired bootstrap 95% CI** for effect size, **Benjamini-Hochberg FDR** across all
   candidates per round, **clustered at the PR/subsystem level** (items from one PR are correlated —
   a **PR-level cluster bootstrap** avoids inflated N / false wins), **≥50 items/stratum, ≥5 seeds**,
   a **pre-registered minimum-uplift threshold**, on the **frozen test set only**.
7. **Power analysis up front** — from P2a's first effect-size estimate, compute the **minimum
   detectable effect** at the planned N/seeds and size the run accordingly; if the wiki's true uplift
   is small we could be underpowered and never know. This also sets the pre-registered min-uplift
   threshold (§6.6) honestly rather than post-hoc.

---

## 7. Promotion (generalization-aware, git-reversible)

Auto-promote a winner **iff**: (a) significant win vs the frozen baseline on the **private held-out
test** (Wilcoxon + BH, min effect size), **AND** (b) **no significant regression on the fastapi
transfer set**. On pass, the winning prompt bodies are auto-written to the working tree
(git-reversible) and `ntfy`'d with the report + diff; the harness **never pushes or merges** — you
review and merge. **Caveat (documented):** the winner generalizes from two *Python* repos; the
read-path prompts are largely language-agnostic (about traversing a markdown wiki + grep, not
language syntax), so the risk is bounded but real — promotion is a hypothesis the transfer gate
guards, not a proof. A second bounded risk the transfer gate also catches: the read prompt can
**overfit to the one frozen reference wiki's idiosyncratic structure** — a win that doesn't survive
on fastapi's differently-shaped wiki is rejected.

**Null result is a success, not a failure.** If no candidate clears the gate, the outcome is
"baseline holds, nothing promoted" — a valid, expected result and the structural defense against
p-hacking pressure to ship *something*. The report says so plainly.

---

## 8. Constraint compliance (brief §4 / §5)

| Constraint | How it's met |
|---|---|
| Ground truth first | Harness self-validated (incl. adversarial configs) before optimizer exists (§6.1). |
| Gold from tooling, not models | AST/LSP/call-graph/PR-diff only; model phrases, never answers (§4). |
| Optimizer ≠ judge | Judge cut from the A loop; where used, gated tiebreaker, distinct family (§2). |
| Strict train/dev/test | Frozen private test + frozen fastapi transfer; gold out of KB + optimizer (§4). |
| Statistical rigor | Wilcoxon + bootstrap CI + BH-FDR, **PR-clustered**, ≥50/stratum, ≥5 seeds (§6.6). |
| Never regress | Promote only on held-out significance **and** transfer non-regression (§7). |
| Red-team defenses | Precision/token hard gates; absent/obfuscated-identifier strata; ablated-agent baseline; hop stratification; prompt-edit validator; canaries (§3–4, §6.5). |
| Thin E2E anchor | Concrete SWE patch-and-test anchor; proxy↔anchor Spearman circuit-breaker (§3). |
| Sandbox everything | Copies of KB + repo; never mutate live (§5). |
| Unattended | **Native deterministic Workflows** (background + journaled `resumeFromRunId`) as the control loop — not an interactive agent loop; cross-workflow SQLite durability; fail-open (`.filter(Boolean)`); per-tier budget hard-stop; `ntfy` on milestone/stall/done/fatal; overnight via always-on host + scheduled wake (§5). |
| Reproducible | Statistical (CI over ≥5 seeds), not bit-exact (agentic SUT); pin temperature/prompt; one SQLite row per cell+round; content-addressed config hashes → free re-runs (§5). |
| Tech stack | Python 3.12+, pydantic v2, `uv`, ruff + `mypy --strict`, pytest, `src/`, SQLite, tree-sitter, `ntfy` for the **LLM-free** harness; all model work via **Claude Code subagents + dynamic Workflows (Opus + Sonnet)** (§1). *(vLLM / free-compute / external API + SDK all de-scoped — no API key.)* |

---

## 9. Phased plan

| Phase | Deliverable | Gate |
|---|---|---|
| **P0** | Discovery — understanding + open questions | ✅ done |
| **P1** | This final design plan | **← here [GATE]** |
| **P2a** | **Hypothesis smoke test (go/no-go)**, plus three architecture checks. (i) Build a decent reference wiki, ~20 single-hop Locate items, run with-wiki vs ablated — **detectable positive uplift at all?** If not, stop and rethink. (ii) Run the smoke test on **both** the Sonnet and Opus SUTs and report **candidate-ranking correlation** — if low, the cheap-search/expensive-gate architecture is invalid (Opus must enter search; bigger budget). (iii) Confirm `agents-scaffold`'s **test suite runs green and stable locally** (the anchor depends on it) and the gold extractor recovers symbol-identity/multi-hop gold at acceptable fidelity. **Recalibrate `max_opus_api_calls` + `max_sonnet_calls` (both metered) from measured per-loop call counts.** | **[GO/NO-GO]** |
| **P2b** | Full eval harness + gold extraction + reference wiki + self-validation (incl. adversarial reward-hack configs) | **[GATE]** |
| **P3** | Frozen-baseline scores (dev + private test + fastapi transfer, with variance) | — |
| **P4** | Random optimizer + GEPA bake-off + prompt-edit validator | **[GATE]** |
| **P5** | Overnight run as chained background **Workflows**. **Dry-run with fault injection first:** stop a Workflow mid-run → relaunch with `resumeFromRunId`, confirm completed cells are cached and only unfinished re-run; kill a subagent → confirm `.filter(Boolean)` skips and the grid continues; exceed budget → clean stop. Then the full run; validate winner on frozen test + transfer. | — |
| **P6** | Report + generalization-gated auto-promotion (git-reversible) | — |

The skill itself (a `SKILL.md` trigger + the Python harness) is authored via `skill-creator` once
P2b's harness shape is proven.

**Scope honesty:** the **harness + gold-extraction + anti-gaming is ~70% of the work and ~all of the
risk**; the optimizer is a thin wrapper once that exists. The whole project rests on the P2a
hypothesis — *if the wiki shows no measurable uplift over a grep-capable agent, there is nothing to
optimize* — so P2a is the first and cheapest kill-switch. Surface **A is the committed deliverable**;
Surface B is a stretch goal for a later phase.

---

## 10. Non-goals & exit criteria

**The harness outlives the optimizer.** Once the Locate/Explain suite + deterministic gold exist,
they are a **standing regression benchmark** for llm-wiki — run on *any* future prompt change to
catch regressions, independent of optimization. That durable asset, not just a one-night winner, is a
primary goal; it is what makes the ~70%-harness effort pay off long-term.

**Non-goals (out of scope — bounds creep):**
- Not tuning the deterministic floor (Doctor / `bundle_ops` / secret scan) — only prompt *text* +
  the named constants.
- Not tuning hook *trigger logic* — only the prompt strings the hooks carry.
- Not multi-language this round (two Python repos; read-path prompts are largely language-agnostic).
- Not a live/continuous optimizer — a discrete overnight run, re-runnable on demand.
- Surface B (capture) is deferred to a later phase.

**Done definition (project exit criteria):** **either** a promoted config with a **statistically
significant, transfer-validated uplift** over the frozen baseline (private test + no fastapi
regression), **or** a **documented null result** ("baseline holds") — *plus*, in both cases, the
**standing regression harness** and the reproducible experiment log. A null result with a working
harness is a successful project, not a failed one.

---

## 11. P2a outcome & learnings (first end-to-end run, `agents-scaffold`)

Built and ran the harness end-to-end against the private `agents-scaffold` repo (599 `.py` files):
clone → tree-sitter gold → item bank → a **blind** 7-concept reference wiki built through the gated
`bundle_ops apply` (Doctor PASS) → SUT-subagent grid via a native Workflow → file-level scoring →
report. **The pipeline works.** Two task batches were run (Sonnet SUT):

- **Single-hop Locate (identifier in the question) is grep-trivial.** Ablated Sonnet ≈ **0.97 F1**;
  wiki uplift ≈ **+0.03 (noise)**; all read-prompt candidates ceiling at ~1.0. Single-hop Locate is a
  **poor discriminator** — it can't measure the wiki's value *or* rank prompts. Keep it only as a
  small control stratum.
- **Multi-file "new-developer change-set" tasks (PR-derived gold) are where the wiki earns its keep.**
  Mean uplift **+0.083**, and **strongly inverse to difficulty**: ~0 where ablated already scores ~0.9
  (nameable/localized), but **+0.14 to +0.32 on the low-baseline items** where a dev must connect
  scattered files. That "helps most where help is needed" shape is the value proposition, confirmed.
- **A real prompt-optimization target exists.** A "read-the-wiki-then-enumerate-the-complete-set"
  prompt **over-fetched** — lower precision than a plain "identify the files" prompt *with* the wiki
  (0.64 vs 0.69), and caused a −0.23 on one item. So the wiki helps, but the read-prompt must balance
  **recall vs precision** — exactly what the optimizer tunes.

**Caveats:** N≈10–20/batch (a signal, **not** significance); some PR titles still carry greppable
identifiers (the absent-identifier *concept* family should sharpen the signal); Sonnet-only.

**Operational findings folded back into the plan:**
- **Throttle Opus.** ~80 concurrent Opus subagents tripped transient *server* rate-limiting (≈38/80
  failed); the search-tier (Sonnet) ran clean. P2b runs Opus in small waves with backoff.
- **Score on the defining file, not the dotted symbol.** The SUT can't reproduce our AST symbol
  identity; "find the right file(s)" is the robust, meaningful matching unit.
- **Item-quality gates that mattered:** skip ambiguous names (defined in >1 file — e.g. Alembic
  `upgrade`); stride-sample across files for breadth; filter to substantive feat/fix/refactor PRs.
- **`args` did not thread** into a Workflow launched by `scriptPath`; runs used an inline script with
  data baked in. The committed `p2a_smoke.mjs` guards loudly if `args` is missing.

**Steer for P2b (revises §9):** lead with **multi-hop / new-developer / concept (absent-identifier)**
strata, single-hop as a small control; scale to **≥50 items/stratum + Wilcoxon/BH significance**;
throttle Opus; the optimizer's first target is the read-prompt's **recall/precision balance**. The
three generators backing these strata ship in the harness: `items.py` (single-hop control),
`pr_items.py` (change-set / explain), `dep_items.py` (reverse-dependency / impact).

### Follow-up runs — concept (absent-identifier) + model-dependence (Sonnet vs Haiku)

Ran the 10 PR-derived items as **absent-identifier capability questions** (no symbol names; gold =
the same PR file sets). Results (best-with-wiki minus the fixed no-wiki baseline, per item; 95% CI =
paired bootstrap):

| SUT | ablated mean | wiki uplift | 95% CI | significant? |
|---|---|---|---|---|
| **Sonnet** (strong) | 0.63 | **+0.059** | [−0.033, +0.177] | **no** (CI ∋ 0) |
| **Haiku** (weak) | 0.54 | **+0.134** (~2.3×) | [−0.020, +0.359] | **no** (CI ∋ 0) |

- A strong Sonnet greps the capability's content words and finds files **with or without** the wiki;
  it clearly helped only where the agent was otherwise *lost* (pr1175 frontend: 0.00 → 0.50).
- The weaker Haiku is worse without the wiki and **gains ~2.3×** the uplift — vivid case pr1467
  (Haiku **0.00 → 1.00**, lost without the map).

**Finding (directional, confirm at N≥50): the wiki's value scales *inversely* with SUT strength and
concentrates where the no-wiki baseline is LOW** — it *rescues a lost agent* (weaker model,
unfamiliar / un-greppable territory) far more than it improves an already-succeeding strong one.
Product implication if confirmed: the wiki lets a cheaper model navigate closer to a stronger one.

**Refined P2b plan:** run the significance test on a **weaker SUT (Haiku)** and **low-baseline
strata**, where the effect is largest and measurable; **≥50 items + Wilcoxon/BH**; the read-prompt
still over-fetches (`map-first` *hurt* several items) — recall/precision balance is the first thing
to optimize. *(All four runs used Sonnet/Haiku Explore subagents; ~16–80 concurrent Opus trips
transient server rate-limiting, so Opus stays in small throttled waves.)*

### The corrective run — a REAL wiki + gotcha-recall (the test we should have run first)

All the above tested a **blind synthetic map** against **file-finding** tasks — both wrong. `agents-scaffold`'s
own `llm-wiki` is **empty**; the real curated bundle is **`homelab/llm-wiki` (78 hard-won gotcha
concepts** — version traps, silent failures, surprising root causes). Re-ran with the right substrate
and task: 12 **symptom-only** questions (Opus-phrased, leakage-checked) whose gold = the concept's
captured root cause; **with-wiki** (read `homelab/llm-wiki`) vs **ablated** (homelab repo, no wiki);
**Opus judge** vs the gold (Sonnet SUT).

| | correct | mean key-facts surfaced |
|---|---|---|
| ablated (repo, no wiki) | 11/12 (92%) | 83% |
| **with-wiki** | **12/12 (100%)** | **100%** |

**Why even ablated scores 92% (a remaining confound): homelab is infrastructure-as-*code* — the fixes
are committed in the repo** (the `ansible.builtin.replace` stripping `-RpvU`, the `pg_read_all_data`
grant, the `ServerSideDiff` annotation), so a strong agent greps the repo and reconstructs the cause.
The wiki is **redundant with the code for already-fixed gotchas.**

**Where the wiki uniquely wins (its irreducible value):**
- **Knowledge not recoverable from code:** `signoz-log-wedge-zookeeper-fsync` — ablated **wrong** (2/6,
  chased the "obvious" cardinality suspect); with-wiki **right** (6/6). The causal chain (ZooKeeper WAL
  fsync stalling on a 3-replica Longhorn volume → ClickHouse session expiry → readonly tables) is
  *runtime* knowledge the IaC doesn't reveal. The one flip.
- **Completeness: +17% facts (83→100%)** — even when ablated was "correct" it missed caveats the wiki
  carried (the durability gap, the *second* Alertmanager, the "it's NOT the obvious suspect" steer).

**Synthesis (the actual answer to "does llm-wiki help"):** value is real but **conditional** — it
concentrates at the intersection of **(a) a weaker agent**, **(b) knowledge not in the code** (subtle
runtime root causes, the *why*, not-yet-committed fixes), and **(c) completeness/caveats**. It adds
little when a strong agent + the code already hold the answer. *llm-wiki pays off for what the code
can't tell you.* Caveats: N=12, not significant; the IaC-encodes-fixes confound *understates* the
value for uncommitted knowledge. **Cleanest next test:** items provably **not** in the repo
(runtime-only / pre-fix / "why is this set oddly") and/or a weaker SUT — to isolate the irreducible value.
