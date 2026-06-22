---
type: Architecture Decision
title: Phase 3 autonomy — hook-driven, auto-default with a guard floor
description: How llm-wiki autonomy works — six wired hook events, a proactive-by-default mode, and the always-on PreToolUse guard floor that makes the default safe.
tags:
  - autonomy
  - hooks
  - phase-3
timestamp: 2026-06-14T00:00:00Z
---
# Phase 3 autonomy — hook-driven, auto-default with a guard floor

Autonomy is implemented entirely as deterministic command hooks in `hooks/hooks.json`
(no model-call hooks). Six events are wired:

- **SessionStart** — preload the root `index.md` plus a mode notice into context.
- **PreToolUse** (matcher `Write|Edit|MultiEdit`, scoped to bundle paths) — `secret_guard.py`
  denies credential writes; `doctor_guard.py` denies non-conformant concept writes (R1/R2).
- **UserPromptSubmit** — a once-per-session *consult* nudge (session-marker-gated): the read loop's
  forcing function, symmetric to capture, so "start smarter" actually happens. Not a per-turn line.
- **PostToolUse** — a nudge after a non-bundle code edit when in an auto mode (mostly silent).
- **Stop** — the end-of-turn capture forcing function: in an auto mode, *only on a turn that
  changed real code* (gated by a `.llm-wiki/capture-pending` marker the PostToolUse hook drops
  and Stop consumes), it blocks the stop *once* (`stop_hook_active`-guarded) so the model decides
  capture-or-stop at the non-disruptive moment the mid-turn nudges miss. Pure-chat turns stay silent.
- **SessionEnd** — a digest pointing at `/llm-wiki:tend`, **emitted only in `curated` mode**; auto modes
  capture silently, so an end-of-session "what I saved" digest is suppressed.

## Mode and the default

Mode resolves from `.claude/llm-wiki.local.md` via `mode.py` and **defaults to `proactive`
(auto) when absent**. This reverses PHASE_PLAN locked-decision-1, which had defaulted to
propose-only (curated).

The write commands (`capture`/`refine`/`prune`/`reorganize`) **honor the mode**: in an auto mode they
apply the gated change directly — no per-write confirmation prompt and no prose recap of what was saved —
and confirm-first only in `curated` mode or when the user explicitly asks to review. (Earlier these
commands were unconditionally confirm-first, which contradicted the advertised auto default.)

## Why an auto default is safe

Two write paths, both gated. A **direct bundle Write/Edit** (ad-hoc, or a concept written in place) is
caught by the always-on **PreToolUse guard floor**: `secret_guard` denies a credential write and
`doctor_guard` denies a non-conformant concept write, regardless of mode. **Command writes**
(`capture`/`refine`/`prune`/`reorganize`) stage in a `/tmp` mirror and land via `cp`, which the floor's
`Write|Edit` matcher does not see — so those are gated *in-command* by a blocking `doctor.py` run plus a
secret scan that **hard-aborts** the apply in an auto mode (where no human reviews the diff). Either way
every write is Doctor-gated, secret-checked, logged, and git-reversible — the worst case of "auto" is a
denied/aborted write, never a leaked secret or a non-conformant bundle.

## Related
- See [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — the rules `doctor_guard` enforces at write time.
