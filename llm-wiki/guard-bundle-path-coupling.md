---
type: Gotcha
title: PreToolUse guards each recompute the bundle path — relocate one, the floor fails open
description: secret_guard and doctor_guard independently derive the bundle root; changing where the bundle lives without updating both silently disarms the auto-mode safety floor.
tags:
  - gotcha
  - hooks
  - secrets
  - doctor
  - autonomy
timestamp: 2026-06-26T14:42:19Z
verified: 2026-06-26T21:36:34Z
---
# PreToolUse guards each recompute the bundle path — relocate one, the floor fails open

**Symptom / context.** Comes up when changing where the wiki bundle lives (e.g. making the
location configurable, or moving it out of `${CLAUDE_PROJECT_DIR}/llm-wiki`). The two PreToolUse
guards — `secret_guard.py` and `doctor_guard.py` — each *independently* recompute the bundle root
as `os.path.realpath(os.path.join(project, "llm-wiki"))` and scope their deny to writes under it
(via `commonpath` / an `_under` check).

**What does not work.** Relocating the bundle (or teaching one guard a new path) while leaving the
other guard's hardcoded join in place. The stale guard computes the *old* root, so
`_under(target, old_root)` is `False` for every write to the **real** bundle, the guard returns
`0` (fails **open**, not closed), and the secret/Doctor floor that makes auto mode safe silently
stops protecting the bundle — with zero signal. There is no error; writes just stop being gated.

**What works.** Route **both** guards through a single shared bundle-path resolver so they can never
diverge — now implemented as `scripts/bundle_path.py` (`bundle_root()`), which both `secret_guard.py`
and `doctor_guard.py` call. Keep `os.path.realpath` **guard-side**, applied to *both* the root and the
target: the resolver returns a *logical* path (expanduser / join / normpath, no realpath), and each
guard realpaths it. `commonpath` is purely lexical, so root and target must be normalized the same way
or the under-check mismatches. (The resolver additionally rejects a root-collapse value — one resolving
to the project root or an ancestor — which would otherwise make the floor scope the whole repo.)

**Why.** The guards fail open by design (an unrelated write must not be blocked), so a wrong root
doesn't error — it just never matches, and the deny never fires. Two copies of the same path
derivation is the footgun; one resolver is the fix. Guard-side realpath keeps symlink semantics
identical across path forms (`~/wiki`, repo-relative, absolute) and preserves the trick where
realpath leaves a not-yet-created tail intact.

## Verify
- plugins/llm-wiki/scripts/secret_guard.py:_bundle_root — wraps the shared `bundle_root()` call from bundle_path.py
- plugins/llm-wiki/scripts/doctor_guard.py — also calls `bundle_root` from bundle_path.py
- run: `grep -n "bundle_root" plugins/llm-wiki/scripts/secret_guard.py plugins/llm-wiki/scripts/doctor_guard.py` — expected: matches in both files

## Related
- See [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — the floor this gotcha can silently disarm.
