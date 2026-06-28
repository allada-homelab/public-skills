---
type: Architecture Decision
title: llm-wiki autonomy — zero-config always-auto with a guard floor
description: How llm-wiki autonomy works — five deterministic hook events, always-on auto (no modes), a PreToolUse guard floor, and background Sonnet subagents that persist and validate.
tags:
  - autonomy
  - hooks
timestamp: 2026-06-14T00:00:00Z
verified: 2026-06-28T05:51:41Z
---
# llm-wiki autonomy — zero-config always-auto with a guard floor

Autonomy is implemented as deterministic command hooks in `hooks/hooks.json` (no model-call hooks).
It is **always on with no config knob**: if the bundle exists, autonomy is on. (The earlier three-mode
system — `proactive`/`curated`/`max` resolved by `mode.py` — was collapsed away.) Five events are wired:

- **SessionStart** — preload the root `index.md` plus a consult nudge into context.
- **PreToolUse** (matcher `Write|Edit|MultiEdit`, scoped to bundle paths) — `secret_guard.py` denies
  credential writes; `doctor_guard.py` denies non-conformant concept writes (R1/R2).
- **UserPromptSubmit** — a once-per-session consult nudge: read the wiki via `/llm-wiki:query` before
  non-trivial work, without asking.
- **PostToolUse** — silently drops a `.llm-wiki/capture-pending` marker after a non-bundle code edit
  (the signal the Stop hook gates on); it emits nothing itself.
- **Stop** — the end-of-turn forcing function: only on a turn that changed real code (the marker gate),
  it blocks the stop *once* (`stop_hook_active`-guarded) so the main agent runs the loop — draft a durable
  finding and dispatch the background `wiki-capturer`, dispatch `wiki-verifier` for any touched `## Verify`
  anchor, else stop. Pure-chat turns stay silent.

## The background model

The main (Opus) agent owns curation judgment; the mechanical work runs on background Sonnet subagents so
the main loop never blocks:

- **`wiki-capturer`** persists an already-decided, already-drafted concept through the gated `apply`
  engine (it does not re-curate).
- **`wiki-verifier`** re-checks a concept whose anchored file changed — on `/query` reads and at
  end-of-turn for anchors the turn touched.

## Why always-auto is safe

Every write is gated. A **direct bundle Write/Edit/MultiEdit** is caught by the always-on **PreToolUse
guard floor**: `secret_guard` denies a credential write and `doctor_guard` denies a non-conformant concept
write. **Command/agent writes** go through `bundle_ops apply`, which stages on a `/tmp` mirror and
**Doctor-gates + secret-scans** before touching the live bundle — a block leaves it byte-for-byte
untouched. Either way every write is Doctor-gated, secret-checked, logged, and git-reversible — the worst
case is a denied/aborted write, never a leaked secret or a non-conformant bundle.

## Verify
- plugins/llm-wiki/hooks/hooks.json — five wired events: SessionStart, PreToolUse, UserPromptSubmit, PostToolUse, Stop
- run: `bash plugins/llm-wiki/scripts/hook_fixtures/run_hooks.sh | grep '^pass='` — expected: `pass=29 fail=0`

## Related
- See [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — the rules `doctor_guard` enforces at write time.
