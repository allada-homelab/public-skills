---
description: Remove a concept, regenerating indexes and logging it.
argument-hint: "[concept path or title] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(python3:*), Bash(date:*), Bash(cp:*), Bash(rm:*), Bash(rmdir:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:prune`. Remove **one** concept and keep the bundle conformant. Per OKF spec
§5 broken links are *tolerated*: inbound links to the removed concept are **reported, never silently
rewritten or deleted**. Use the `wiki` skill for format rules.

**Writes always apply directly.** There is no confirm-first path: stage the removal on a mirror, gate it
with the Doctor, and apply — **no confirmation prompt and no prose recap**. The inbound-link warning
(step 3) is surfaced either way. The safety net is the staged Doctor gate (blocking) and
git-reversibility; prune only removes content, so no secret scan applies.

Arguments: `$ARGUMENTS` may carry a concept path/title and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up).
   None → stop: there is no wiki here yet (one is created automatically on the first `/llm-wiki:capture`),
   so there is nothing to prune.
2. **Identify the target concept.** Grep/Glob from the hint; on ambiguity, list candidates and ask;
   none found → say so and stop. Never guess which concept to delete.
3. **Warn about inbound links.** Grep the bundle for links to the concept (both `./…` and `/…` forms).
   List every referencing file so the user sees what will dangle. These are **not** auto-fixed.
4. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`; capture the date once
   (`today=$(date -u +%F)`, reused in step 6); then:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" remove "$mirror" --concept <relpath>`
   - **Emptied-subdir cleanup.** If the removal leaves the concept's subdirectory holding **nothing but
     `index.md`** and it is **not** the bundle root, `rm` that `index.md` then `rmdir` the directory
     (`rmdir`, not `rm -rf`, so a still-occupied dir fails loud rather than deleting real content). The
     `index` regen below rewrites the root and any surviving `index.md` even when it drops to **zero**
     concepts, so no stale bullet to the removed concept lingers.
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Update --message "Removed [<title>](./<relpath>)." --date "$today"`
5. **Doctor gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format json`.
   Exit ≠ 0 → show violations, `rm -rf "$mirror"`, write nothing. The now-dangling inbound links appear
   as `R4` WARNINGs (report-only, expected) — surface them so the user can `capture`/`reorganize` later.
6. **Apply.** No secret scan is needed — prune only removes content. Apply now without asking and
   **without a prose recap**. Reproduce on the real bundle (the steps are deterministic: same `remove` →
   emptied-subdir cleanup → `index` → `log-append … --date "$today"`), then run the Doctor on the real
   bundle to confirm PASS — and verify the regenerated `index.md` no longer lists the removed concept (a
   lingering `R4` to it means the index didn't refresh). If a write/step fails, report exactly what landed.
   Clean up only a real mirror (`rm -rf "$mirror"` — never an unset path).

Rollback: the deletion is recoverable from git history **only if the concept was previously committed**
(a never-committed concept is not) — the inbound-link report in step 3 is your cue to slow down if the
concept looks load-bearing.
