# /llm-wiki — Phase 3 Technical Plan

> **Status: 🚧 3a–3c shipped (test-first); only the Max tail remains.** "Make It Autonomous" — cross
> the hooks cliff: from user-invoked-only to a wiki that preloads context, auto-captures, and
> self-guards, with **auto (Proactive) as the default**. 3a: autonomy mode + SessionStart preload. 3b:
> the PreToolUse safety floor (blocking secret guard + per-file Doctor guard). 3c: UserPromptSubmit +
> PostToolUse capture nudges, the SessionEnd digest, and the `/tend` curation command. 3c′ (dogfood
> follow-up): a **Stop** hook (`hook_stop.py`) as the end-of-turn capture forcing function. Six hook
> events wired (SessionStart, PreToolUse, UserPromptSubmit, PostToolUse, Stop, SessionEnd); hook corpus
> green (`pass=25 fail=0`). The loop is confirmed live (UserPromptSubmit + the two PreToolUse guards
> verified end-to-end in a real session). Deferred: the **Max** background-subagent tail (runtime spike, §6).
>
> Companion to [`PHASE_PLAN.md`](../planning/PHASE_PLAN.md) and the
> [Phase 1](./phase-1-tech-plan.md) / [Phase 2](./phase-2-tech-plan.md) plans. Hook capabilities below
> were **verified against current Claude Code docs** (hooks.md, plugins-reference) before scoping — see §7.

## 1. Overview

Phase 3 adds autonomy on top of the Phase 1 author/read loop and the Phase 2 maintenance engine. It
ships: an **autonomy-mode** mechanism (default **Proactive/auto**), a **SessionStart** context preload,
**during-work auto-capture**, a **blocking secret guard** + per-file **Doctor guardrail** (PreToolUse),
a **SessionEnd digest**, and an on-demand **`/tend`** command. The Max-mode background-subagent tail is
**deferred** pending a runtime spike (§6).

## 2. Locked-decision change: default = Proactive (auto)

PHASE_PLAN locked-decision-1 set the mode-absent default to **Curated** (propose-only) to avoid silent
writes on a fresh checkout. **This phase reverses that to Proactive (auto), by owner decision
(2026-06-14).** The reversal is only safe *because Phase 3 ships the guards that contain it*, all in the
same phase as the unattended writes:

- every unattended write passes the **blocking secret guard** (redacts before disk) and the **per-file
  Doctor guardrail** (R1/R2);
- every write routes through the Phase 2 engine (conformant indexes/log) and is **logged + git-reversible**;
- a **SessionEnd / `/tend` digest** surfaces what landed for review.

Curated (propose-only) and Max remain selectable via the mode file. A one-line SessionStart notice
states the active mode and how to switch. Residual accepted risk: model-authored *content* (not just
structure) can land without per-write human review — mitigated, not eliminated, by the floor + digest.

## 3. Autonomy mode

- **Storage:** `${CLAUDE_PROJECT_DIR}/.claude/llm-wiki.local.md` (git-ignored, per-project). A single
  `mode: proactive | curated | max` line (markdown so it's human-readable).
- **Resolution (`scripts/mode.py`):** absent / unreadable / unrecognized ⇒ **`proactive`** (the new
  default). Deterministic; the hooks and commands call it.
- **Semantics:** `curated` = propose-only (auto-capture surfaces a candidate but does not write);
  `proactive` = auto-write (gated by the floor); `max` = proactive + the deferred background tail.

## 4. Hooks (declared in `plugins/llm-wiki/hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}`-rooted)

| Event | Type | Behavior | Mode-gated? |
|---|---|---|---|
| **SessionStart** | command | If a bundle exists, inject root `index.md` + the active-mode notice via `additionalContext`; skip silently if none. | no (always preload) |
| **PreToolUse** (`Write\|Edit\|MultiEdit`) | command | **Secret guard** + **Doctor guardrail**, scoped by a bundle-path check. Deny on hard violations; **redact secrets via `updatedInput`**. Runs on *every* write path regardless of mode. | no (always) |
| **UserPromptSubmit** | command | Cheap signal that the turn may carry a capture-worthy finding; inject a capture nudge (Proactive) or a propose nudge (Curated). | yes |
| **PostToolUse** | command | Cheap pre-filter; escalate to capture only on a hit. Never a per-tool model call. | yes |
| **SessionEnd** | command | Emit a digest of what changed this session. | no (always digest) |

All are **command** hooks (deterministic shell/python), never model-call hooks. Hook-config changes
require `/reload-plugins` or restart — the install/upgrade flow must say so.

## 5. The safety floor (PreToolUse) — lands before any unattended write (3b)

- **`scripts/secret_guard.py`** — PreToolUse wrapper reading the event JSON (`tool_input.file_path` +
  content). If the target is a bundle file and `secret_scan.py` flags content, either **deny** (with a
  reason) or return **`updatedInput`** with secrets redacted to `<REDACTED:type>`. Non-bundle paths pass
  through untouched (matcher + path guard).
- **`scripts/doctor_guard.py`** — PreToolUse wrapper enforcing only **per-file hard rules** (R1/R2 on a
  concept's proposed content; index/log are engine-owned and multi-file, so they stay in command
  orchestration, not the hook). Writes proposed content to a temp file and runs `doctor.py` on it.

## 6. Deferred: Max background-subagent tail

My hook-capability check confirmed that (a) spawning a **detached background subagent from a hook** and
(b) whether plugin **PreToolUse hooks propagate into a subagent's writes** are **not documented** in
current Claude Code. Per locked-decision-2, Max is **not built** until a live runtime spike confirms the
dispatch mechanism *and* gate propagation. If the spike fails, Max uses the (separately deferred) `/loop`
approach. `/loop` out-of-session curation stays deferred past Phase 4 (locked-decision-3).

## 7. Verified hook facts (current Claude Code)

- SessionStart injects context via `{"hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "…"}}` on stdout. ✓
- PreToolUse can **deny** (`permissionDecision: "deny"` + reason), sees full `tool_input`, scopes via a
  `matcher` (e.g. `Write|Edit|MultiEdit`), and can **modify input via `updatedInput`** (→ redaction). ✓
- Plugin hooks: `hooks/hooks.json` or `plugin.json`; `${CLAUDE_PLUGIN_ROOT}` substituted; changes need
  `/reload-plugins`/restart. ✓
- Hook types: command / http / mcp_tool / prompt / agent; commands support `"async": true`. ✓
- **Undocumented (→ Max deferred):** hook→detached-subagent dispatch; plugin-hook propagation into
  subagent contexts.

## 8. Tests (TDD)

Hooks are command scripts with JSON stdin→stdout contracts — tested like the Doctor. New
`scripts/hook_fixtures/` corpus: each case feeds an event JSON on stdin (+ a staged bundle / env) and
asserts the hook's emitted decision (`deny` / `allow` / `updatedInput` / `additionalContext`) and exit
code. Coverage targets: secret guard (planted key → redact/deny; clean → allow; non-bundle path →
ignore), Doctor guardrail (missing `type` → deny; valid → allow), mode resolver (absent → proactive;
each explicit mode), SessionStart (bundle present → injects index + mode; absent → empty).

## 9. Sub-phasing

- **3a** ✅ — mode mechanism (`mode.py`) + SessionStart preload hook (`hook_session_start.py`).
- **3b** ✅ — secret guard (`secret_guard.py`) + Doctor guardrail (`doctor_guard.py`), both PreToolUse
  (`Write|Edit|MultiEdit` + bundle-path scope), deny on hit. The floor; precedes any unattended write.
- **3c** ✅ — during-work auto-capture: `hook_user_prompt.py` (UserPromptSubmit, terse mode-aware nudge —
  capture in proactive, propose in curated) + `hook_post_tool.py` (PostToolUse pre-filter — nudges only
  after a *non-bundle* code edit in an auto mode; silent for bundle writes / curated / no bundle, so it
  isn't a per-call model call; tunable if noisy) + `hook_session_end.py` (SessionEnd plain-text digest of
  the newest log day, pointing at `/tend`; observe-only, surfaces via the transcript) + the `/tend`
  on-demand curation command.
- **3c′** ✅ *(dogfood-driven follow-up)* — `hook_stop.py` (Stop, the end-of-turn capture **forcing
  function**). Dogfooding in a real repo showed the 3c mid-turn nudges get deferred in favour of the
  in-flight task, so durable findings slip by. The Stop hook fires when the turn is finishing — the
  non-disruptive moment — and in an auto mode emits `{"decision":"block", reason, hookSpecificOutput.
  additionalContext}` (exit 0) to continue *once*, making the model decide capture-or-stop. Loop-guarded
  by `stop_hook_active` (true on the re-fire → allow stop); silent in curated / no-bundle. The model is
  the judge (a deterministic hook can't know a finding occurred); the reason text gives a clean
  "nothing durable → just stop" out. Tunable: a transcript-tail gate (fire only when files changed this
  turn) is the first refinement if the per-turn continuation proves noisy.
- **3d** *(out of this phase)* — Max tail, only after a passing runtime spike.

## 10. Exit criteria

With Proactive (default): a correction/finding yields an auto-captured, logged, conformant concept; a
planted secret in any write is redacted/denied before disk and the file still passes the Doctor;
SessionStart preloads the root index + mode notice; Curated suppresses silent writes while still
preloading; `/tend` produces a no-destructive-change digest. Every write conformant, every change
logged, nothing destructive without a recoverable trail. Install flow surfaces the `/reload-plugins`
requirement for hook changes.
