---
type: Architecture Decision
title: Phase 3 autonomy — hook-driven, auto-default with a guard floor
description: How llm-wiki autonomy works — five wired hook events, a proactive-by-default mode, and the always-on PreToolUse guard floor that makes the default safe.
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
- **SessionEnd** — a digest pointing at `/llm-wiki:tend`.

## Mode and the default

Mode resolves from `.claude/llm-wiki.local.md` via `mode.py` and **defaults to `proactive`
(auto) when absent**. This reverses PHASE_PLAN locked-decision-1, which had defaulted to
propose-only (curated).

## Why an auto default is safe

The always-on **PreToolUse guard floor** is what makes a proactive default safe: every
autonomous write is secret-scanned (`secret_guard`), Doctor-gated (`doctor_guard`), logged,
and git-reversible. The floor holds regardless of mode, so the worst case of "auto" is a
denied write — never a leaked secret or a non-conformant bundle.

## Related
- See [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — the rules `doctor_guard` enforces at write time.
