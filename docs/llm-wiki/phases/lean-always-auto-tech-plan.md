# Lean always-auto llm-wiki — tech plan

Status: **design approved, not yet implemented** (2026-06-28).
Branch: `llm-wiki-lean-autonomy`.

## Goal

Make the llm-wiki plugin **zero-config and always-on auto**, **lean the surface** from 10 commands
to 6 by merging/cutting, move proactive **persistence and validation to background Sonnet
subagents** (the main agent decides *what*, a subagent does the mechanical work), and **consolidate
the gated-write pipeline** into one tested engine subcommand so the safety envelope lives in one
place instead of being hand-copied across commands.

## Non-goals

- No change to OKF conformance rules **except** cutting R5 (lonely-subdir, a report-only taste rule).
- No change to the Doctor's `--mode strict|lenient` flag — that is unrelated to autonomy mode.
- No reintroduction of configurable bundle location (intentionally reverted earlier).

## 1. Zero-config, always-on auto

Today three autonomy modes exist (`proactive` default, `curated`, `max`) resolved from
`.claude/llm-wiki.local.md` by `scripts/mode.py`. Collapse to a single always-auto behavior with
**no config knob**: if the bundle exists, autonomy is on.

- **Delete `scripts/mode.py`** and every `from mode import resolve_mode` import + branch.
- `hook_post_tool.py`: remove the mode gate → drop the `capture-pending` marker whenever a
  non-bundle code edit happens and the bundle exists.
- `hook_stop.py`: remove the mode gate → the end-of-turn forcing function fires whenever the marker
  is set (still `stop_hook_active`-guarded; blocks once).
- `hook_session_start.py`: remove the `MODE_NOTE` dict and the `Active mode: …` preload line; keep
  the index preload + `CONSULT_GUIDANCE`.
- **Delete `hook_session_end.py`**, its `SessionEnd` entry in `hooks/hooks.json`, and its fixtures —
  the end-of-session digest is low value once captures happen organically (SessionStart preload +
  `/tend` cover it).
- Remove the `mode:` config concept from all docs.

## 2. Command surface: 10 → 6

Survivors: **`query`**, **`capture`**, **`prune`**, **`reorganize`**, **`tend`**, **`ingest`**.

- **Cut `init`** → auto-bootstrap. The first write (manual `capture` or background `wiki-capturer`,
  and `ingest`) creates a conformant empty bundle (`index.md` + `log.md`) if absent, via the engine
  (see §3). Remove all "Run `/llm-wiki:init` first" messaging; nothing to register.
- **Cut `conform`** → folded into `tend`, which already runs the Doctor as its first step. A raw
  check is `python3 scripts/doctor.py <bundle>`; no dedicated command earns its place.
- **Merge `explore` → `query`.** `query` answers a question *and* supports browse-from-a-point
  (read `index.md`, follow links — which Claude does natively). Delete `explore.md`.
- **Merge `refine` → `capture` (upsert).** `capture` becomes create-or-edit: if the target concept
  file exists it edits in place, otherwise it creates. New-vs-existing is decided by file existence.
  Delete `refine.md`. One gated pipeline.
- **Keep `prune`, `reorganize`, `ingest`** unchanged in purpose (`ingest` still fans out
  `wiki-explorer`; `reorganize` still does link-preserving move via `bundle_ops move`).

## 3. Gated-write pipeline consolidation: `bundle_ops apply`

Today the safety-critical envelope (stage a `/tmp` mirror → write → regenerate index →
`log-append` → **Doctor-gate** → **secret-scan** → `cp` back → re-Doctor) is hand-copied across the
write commands. With a new background writer (`wiki-capturer`) that would become a 3rd/4th copy.
Instead, add a single tested engine subcommand.

- **`bundle_ops.py apply <bundle> --concept <relpath> --content-file <path> [--log-kind <kind>]
  [--log-message <msg>] [--date <YYYY-MM-DD>]`**:
  1. **Ensure** the bundle exists — if `index.md`/`log.md` are absent, create a conformant empty
     bundle (absorbs `init`).
  2. **Stage**: copy the live bundle to a `mktemp` mirror; write the concept content into the mirror
     at `<relpath>`.
  3. **Regenerate** the mirror's index (`bundle_ops index`) and append the log entry.
  4. **Doctor-gate** (strict): on any ERROR → exit non-zero, emit the violations, leave the live
     bundle **untouched**.
  5. **Secret-scan** the staged concept: on any hit → exit non-zero, emit the redacted finding,
     leave the live bundle untouched.
  6. **Commit**: `cp` the gated mirror's changed files into the live bundle; re-run index/log against
     the live bundle; re-Doctor to confirm PASS. Clean up the mirror. Emit a JSON status
     (`applied | blocked:doctor | blocked:secret`).
- Output is JSON so callers can branch deterministically.
- **Callers**: `capture` (manual upsert) and `wiki-capturer` (background) call `apply` directly.
  `prune`/`reorganize` keep their `bundle_ops remove`/`move` operation but reuse the same Doctor +
  secret-scan gate step (extract a shared gate helper rather than re-prose it).
- **Tests (TDD, before implementing)**: ops-fixtures for `apply` — clean success; Doctor-blocked
  (non-conformant concept → live bundle unchanged); secret-blocked (planted credential → unchanged);
  auto-init into an empty/absent bundle.

## 4. Background persist + validate (Sonnet subagents)

The **main (Opus) agent keeps all curation judgment**; subagents do mechanical work.

- **New `agents/wiki-capturer.md`** (model: sonnet; tools: Read, Grep, Glob, Bash, Write). Input: a
  *drafted* concept from the main agent — title, type, slug/relpath, body, tags, and the `## Verify`
  anchor (authored per `concept-template`). It writes the content to a temp file and calls
  `bundle_ops apply` to persist it (gated). It reports a terse status and **does not re-decide
  whether to capture** — the main agent already made that call.
- **`agents/wiki-verifier.md`** (existing, sonnet): behavior unchanged. Now *also* dispatched
  proactively at end-of-turn (see below), in addition to the `/query`-time freshness path.
- **`hook_stop.py` forcing prompt** (the text it blocks the stop with) is rewritten to instruct the
  main agent: *(1)* if this turn established a durable finding, draft it per the wiki skill and
  dispatch `wiki-capturer` in the background to persist it; *(2)* grep the bundle's `## Verify`
  anchors for any concept naming a file you changed this turn and dispatch `wiki-verifier` (background)
  for each; *(3)* then stop. Marker-gated (only on real-code turns); fire-and-forget (main loop never
  blocks on the subagents).
- **`SKILL.md`** documents this loop explicitly: read via `/query` before non-trivial work **without
  asking the user**; at end of work, decide + draft + dispatch `wiki-capturer`; dispatch
  `wiki-verifier` for touched anchors. Main owns judgment; Sonnet executes.

## 5. Function cuts

- **Delete the `consultations.json` popularity counter** (was in `explore`/`query`; `tend` reads it
  for a staleness tiebreaker). `tend` already ranks by timestamp + newest-log + git; drop the counter
  read there too.
- **Cut `doctor.py` R5 `check_lonely_subdirs`** + its fixtures + every R5 reference in docs/skill.
- **Keep `doctor.py _has_flow_collection`** (one actionable diagnostic; not worth the churn).

## 6. Proactive-reading emphasis

`SKILL.md` + the `UserPromptSubmit` and `SessionStart` nudges make "consult `/query` before
non-trivial work, without asking the user" the explicit default expectation (today it is a softer
once-per-session nudge).

## 7. Testing & gates

- **Remove fixtures**: `mode_absent`, `mode_curated`, `mode_garbage`, `mode_max`, `post_tool_curated`,
  `stop_curated`, `session_end_*`, and the R5 lonely-subdir Doctor fixture(s).
- **Update fixtures**: `post_tool_*`, `stop_*`, `session_start_*` to drop mode config and assert the
  unconditional always-auto behavior.
- **Add fixtures**: `bundle_ops apply` ops-fixtures (§3); any new `prune`/`reorganize` shared-gate
  coverage.
- Recompute all three corpus counts and update `CLAUDE.md`. Agent prose (`wiki-capturer`) is not
  gate-covered (like the other agents); the pipeline it calls (`apply`) is.

## 8. Docs

- `CLAUDE.md`: rewrite the autonomy section (zero-config always-auto), the command list (6),
  background agents, the `apply` engine, and counts.
- `README.md`: update command list + autonomy description.
- `SKILL.md` + references: remove mode language; document upsert `capture`, merged `query`, the
  proactive loop; remove R5 and the consult counter.

## 9. Rollout (gated waves, mirroring the prior overhaul)

Feature branch `llm-wiki-lean-autonomy`; full gate suite (Doctor / ops / hooks fixtures + dogfood
Doctor) green after each wave:

1. **Mode collapse + cuts** — delete `mode.py`, de-mode hooks, cut `hook_session_end`, cut R5 + the
   consult counter, remove `mode_*`/`session_end_*` fixtures.
2. **Engine consolidation** — `bundle_ops apply` (+ auto-init) with ops-fixtures; shared gate helper.
3. **Command merges/cuts** — `capture` upsert (absorb `refine`), `query` absorb `explore`, cut
   `conform`/`init`, rewire survivors to `apply`.
4. **Background agents + hook rewiring** — `wiki-capturer`, `hook_stop` forcing prompt, proactive
   verifier dispatch, SKILL proactive loop.
5. **Docs + fixture reconciliation** — CLAUDE.md/README/SKILL, recount, dogfood-bundle anchor sweep
   (the `## Verify` anchors that the changes invalidate).

## Risks & mitigations

- **Curation quality of background persist** — mitigated: the main agent decides *what* and drafts;
  Sonnet only persists.
- **Auto-bootstrap correctness** — the first write must yield a Doctor-PASS empty bundle; covered by
  an `apply`-into-empty ops-fixture.
- **`apply` touches the safety floor** — TDD with the block-on-Doctor and block-on-secret fixtures
  before wiring any caller to it.
- **Breaking change**: removing `curated` mode changes behavior for anyone relying on confirm-first.
  Acceptable per explicit direction; call it out in the commit/PR.
- **Self-invalidated docs**: the change will stale some dogfood `## Verify` anchors (e.g. fixture
  counts) — wave 5 sweeps and re-stamps them (a lesson from the prior overhaul).
