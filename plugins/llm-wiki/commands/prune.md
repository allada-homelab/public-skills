---
description: Prune (remove) a concept from the llm-wiki, regenerating indexes and logging the removal.
argument-hint: "[concept path or title] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Edit, Bash(python3:*), Bash(cp:*), Bash(rm:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:prune`. Remove **one** concept and keep the bundle conformant. Per OKF spec
§5 broken links are *tolerated*: inbound links to the removed concept are **reported, never silently
rewritten or deleted**. Use the `wiki` skill for format rules. **Confirm-first: write nothing to the
real bundle until the user approves the diff.**

Arguments: `$ARGUMENTS` may carry a concept path/title and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up).
   None → stop: "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Identify the target concept.** Grep/Glob from the hint; on ambiguity, list candidates and ask;
   none found → say so and stop. Never guess which concept to delete.
3. **Warn about inbound links.** Grep the bundle for links to the concept (both `./…` and `/…` forms).
   List every referencing file so the user sees what will dangle. These are **not** auto-fixed.
4. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`; then:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" remove "$mirror" --concept <relpath>`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Update --message "Removed [<title>](./<relpath>)." --date <today>`
5. **Doctor gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format json`.
   Exit ≠ 0 → show violations, `rm -rf "$mirror"`, write nothing. The now-dangling inbound links appear
   as `R4` WARNINGs (report-only, expected) — surface them so the user can `refine`/`reorganize` later.
6. **Diff & confirm.** Show `diff -ru "<bundle>" "$mirror"` (the deleted file, regenerated indexes, log
   append). No secret scan is needed — prune only removes content. On approval, reproduce on the real
   bundle (the steps are deterministic: same `remove` → `index` → `log-append … --date <today>`), then
   run the Doctor on the real bundle to confirm PASS. On decline, do nothing. Clean up only a real
   mirror (`rm -rf "$mirror"` — never an unset path).

The deletion is recoverable from git history — name that as the rollback when you confirm.
