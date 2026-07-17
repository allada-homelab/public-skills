# LLM Wiki

llm-wiki is a knowledge coprocessor for Claude Code. It quietly turns a repository wiki into working
memory: recall arrives before a task, deep reading happens in disposable contexts, code changes wake an
impact radar and Scribe, and unanswered questions can become bounded background research. The result is
a project that gets easier for agents to work in as a side effect of ordinary development.

Knowledge stays portable and reviewable as Markdown in Google's
[Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).
There is no server, vector database, or required setup ritual.

```text
prompt → metadata candidates → forked context capsule → grounded work
       → changed-path evidence → impact radar + Scribe → better future recall
                         GAP → bounded research → quarantine or Scribe
```

## What feels magical

- **Proactive, context-clean recall.** A recursive metadata catalog selects likely concepts without
  opening their bodies. Glimmer, Oracle, or Archaeologist then reads them in a `context: fork` Sonnet
  context and returns only a ≤4 KB cited capsule. The main conversation gets the answer, not the
  research exhaust.
- **Adaptive depth and parallel evidence.** Deterministic routing chooses fast/direct, normal synthesis,
  or deep history/contradiction work plus an implementer, debugger, reviewer, operator, newcomer, or
  historian lens. Oracle and Archaeologist can fan out across disjoint wiki sections under hard budgets;
  only one synthesizer speaks back.
- **Change-impact radar.** Exact changed-path evidence is mapped back to concepts, Verify anchors, and
  transitive concept links. A read-only background Sentinel separates direct high-confidence impact
  from quiet shadow hypotheses.
- **Background Scribe.** Normal project edits freeze an immutable evidence packet. Scribe decides whether
  one finding is durable, deduplicates it, attaches stable claim/evidence provenance, and publishes at
  most one concept through the deterministic gate—or silently skips.
- **A self-filling knowledge loop.** An `insufficient_evidence` capsule may propose a structured gap.
  The causal controller deduplicates it by normalized question, scope, and repository revision, then a
  high-effort Sonnet researcher reads an exact safe source manifest. Objective code-plus-test findings
  may flow to Scribe; policy, intent, security, production, weak, or conflicting conclusions are
  quarantined outside recall.
- **Monorepo-scale ingest.** Up to three read-only Sonnet Explorers inspect disjoint, code-owned manifests
  in parallel. Explicit `--into` placement wins; otherwise only a unique match to existing topology is
  used. One coordinator deduplicates and lands one provenance-backed, Doctor-gated batch.

## Safety and autonomy

Every autonomous job has a causal run/job ID, role, idempotency claim, deadline, call/turn/time budget,
descendant limit, one retry, cancellation behavior, cooldown, and feature/global kill switch. Workers
cannot publish. Plugin-origin writes do not recursively arm Scribe, impact, or gap work.

Wiki, repository, diff, and model text are evidence, never instructions. Read-only coprocessors use
explicit tool allowlists and a path hook that keeps them inside the repository and away from common or
configured sensitive paths. `run:` Verify anchors are disabled. Every plugin-owned publication passes:

1. current HEAD/source-hash preflight;
2. stable observed/inferred/contested provenance with objective roots;
3. credential/secret scanning;
4. strict deterministic OKF Doctor validation;
5. one locked, git-reversible bundle apply.

Background work is best-effort and session-scoped in v1. llm-wiki does not promise same-PR or cross-session
completion, and the preflight does not claim a race-free compare-and-swap boundary.

## Install

```text
/plugin install llm-wiki@<your-marketplace>
/reload-plugins
```

Once a `llm-wiki/index.md` exists, recall and learning are on by default. The first explicit capture
or ingest can initialize the bundle.

## Commands

The coprocessor loop is automatic; these seven commands are the manual control surface.

| Command | Purpose |
|---|---|
| `/llm-wiki:query <question>` | Compile a cited answer in an isolated context, or browse indexes directly. |
| `/llm-wiki:capture [finding] [--into section]` | Explicitly upsert one Doctor/secret-gated concept. |
| `/llm-wiki:ingest [repo] [--scope min\|medium\|high] [--into section] [--dry-run]` | Bootstrap grounded concepts with bounded parallel Explorers and one batch publication. |
| `/llm-wiki:tend` | Produce a read-only curation and conformance digest. |
| `/llm-wiki:prune [concept]` | Remove one concept and report dangling inbound links. |
| `/llm-wiki:reorganize [what]` | Move/rename concepts while rewriting links. |
| `/llm-wiki:resolve` | Repair engine-owned `index.md`/`log.md` merge conflicts and re-run Doctor. |

All accept `--bundle <path>` where relevant. The default is
`${CLAUDE_PROJECT_DIR}/llm-wiki`.

## Configuration

Defaults are intentionally useful. Optional flat YAML frontmatter in
`.claude/llm-wiki.local.md` can tune:

```yaml
---
capture_nudge: on
capture_min_edits: 1
sensitive_paths: private/, fixtures/secrets/
autonomy: on
autonomy_disabled: impact
autonomy_max_calls: 12
autonomy_max_turns: 120
autonomy_max_seconds: 480
autonomy_max_descendants: 4
autonomy_max_depth: 2
autonomy_cooldowns: scribe=30,gap=300,impact=30
---
```

All plugin-owned reasoning agents declare `model: sonnet`; deterministic parsing, ranking, hashing,
state, gating, and publication use Python instead of a cheaper model. Installation/environment model
overrides still participate in Claude Code precedence, so organizations requiring a strict floor must
also enforce their managed model policy. A one-hop Sonnet→Opus escalation path is deliberately deferred.

## Storage and team workflow

One Markdown file is one concept. Recursive `index.md` files provide progressive disclosure; `log.md`
is chronological; relative `./` links form the knowledge graph. Generated session/controller/evidence
state lives under gitignored `llm-wiki/.llm-wiki/`.

Concept files usually merge independently. `/llm-wiki:resolve` union-merges `log.md`, regenerates
indexes, and re-gates the bundle when engine-owned files conflict. Human-edited concept conflicts still
need human reconciliation. Because the wiki is ordinary git content, rollback is a normal revert.

## Development

The runtime and deterministic engine are Python 3 stdlib only. The network-free gate is:

```bash
python3 -B evals/run.py --deterministic
```

Shared bounded v1 packet contracts are in `scripts/packet_contracts.py`.
