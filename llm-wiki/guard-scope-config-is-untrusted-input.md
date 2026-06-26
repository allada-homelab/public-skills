---
type: Gotcha
title: Config that steers a security guard's scope is untrusted input — validate in the resolver, not the UI
description: When a guard derives what it protects from configurable input, a committed/shared config is attacker-controllable; enforce provenance + containment where the guard reads it, not only in the prompt that writes it.
tags:
  - gotcha
  - secrets
  - doctor
  - hooks
  - autonomy
timestamp: 2026-06-26T16:07:02Z
---
# Config that steers a security guard's scope is untrusted input — validate in the resolver, not the UI

**Symptom / context.** A PreToolUse guard scopes its deny to "writes under the bundle," and the bundle
location became configurable (`bundle_path:` resolved by `scripts/bundle_path.py`, read by both guards).
Anything that *steers where the guard looks* is now part of the trust boundary.

**What does not work.** Enforcing the safety rule ("a repo-shared, committed `.claude/llm-wiki.md` may
only name a repo-relative path") **only in the `/llm-wiki:init` prompt**. The prompt is a convenience;
a hand-edit or a PR bypasses it entirely. A committed file is teammate/attacker-controllable: a
`bundle_path: ~/.ssh` or `../../etc` merged via PR would, on a teammate's next session, silently
redirect their guard scope (and, under the proactive default, their auto-mode writes) off-repo — with
only a warning. Equally, **any** value resolving to the project root or an ancestor (`.`, `..`, `/`,
empty) collapses the under-bundle check onto the whole repo.

**What works.** Put the invariants in the **resolver** that the guards call, keyed on value *provenance*:
- a value from the *committed* file is honored only if repo-relative **and** repo-contained
  (`os.path.commonpath([resolved, project]) == project`); `~`/absolute/`..`-escape are rejected and
  fall through. A self-chosen per-user (`.local.md`/`--bundle`) value may point anywhere (the
  out-of-repo *warning* covers reversibility).
- reject **any** source whose result is the project root or an ancestor
  (`commonpath([resolved, project]) == resolved`) — the root-collapse guard.
A rejected value falls through to the next layer, then the default, so the floor degrades safe.

**Why.** Guards fail *open* by design (an unrelated write must not be blocked), so a wrong/over-broad
root never errors — it just stops matching, and the deny silently never fires. UI validation can't
defend a value the UI never saw. The control has to sit at the single point of truth the guards actually
read; that is also what makes the out-of-repo warn-don't-block policy sound (every off-repo bundle is
then provably self-chosen).

## Related
- See [PreToolUse guards each recompute the bundle path — relocate one, the floor fails open](./guard-bundle-path-coupling.md) — why both guards must share this one resolver in the first place.
- See [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the floor these invariants protect.
