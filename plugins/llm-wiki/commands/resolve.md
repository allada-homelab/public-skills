---
description: Resolve git merge conflicts in the wiki bundle (union log.md, regenerate index.md, re-gate).
argument-hint: "[--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(python3:*), Bash(git:*)
---

You are running `/llm-wiki:resolve`. Resolve **git merge conflicts inside the wiki bundle** the
deterministic way: the engine unions `log.md` (both sides' bullets under their `## YYYY-MM-DD` headings,
deduped, newest-first), discards conflicted `index.md` content and regenerates every index from concept
frontmatter, then re-runs the Doctor. Concept files are **not** conflict-resolved here — reconcile a
conflicted concept by hand (or with git) first; this command owns the engine-authored reserved files
(`index.md` / `log.md`). Use the `wiki` skill for format.

Arguments: `$ARGUMENTS` may carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk
   up from the cwd for a root `index.md`). **None → there is no wiki here yet** (one is created
   automatically on the first `/llm-wiki:capture`), so there is **nothing to resolve** — say so and stop.

2. **Run the merge engine.** Run:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" merge "<bundle>"
   ```

   It serializes on the bundle lock, prints a one-line JSON status to stdout, and never hand-edits a
   concept. Branch on the JSON `status`:
   - **`clean`** (exit 0) → no conflict markers were found in `log.md` or any `index.md`; say **nothing
     needed conflict resolution** and stop.
   - **`merged`** (exit 0) → the conflicts were resolved. Report what was reconciled from the JSON
     `resolved` array — `log.md` was **union-merged** (both sides' bullets kept, deduped, newest-first)
     and each listed `index.md` was **discarded and regenerated** from concept frontmatter — then remind
     the user to **`git add` the resolved files and finish the merge/commit** (the engine writes the files
     but does not stage them).
   - **`blocked:doctor`** (exit 1) → the merged files were written but the post-merge Doctor found
     **conformance errors**. Show the JSON `violations` (each an object naming the failing `rule`, `file`,
     `line`, and `message`) and the `hint` verbatim; the merged files were **left in place for
     inspection**. The conflict markers are already consumed at this point, so re-running this command
     reports `clean` **without re-checking conformance** — do not use it to confirm the fix. Instead, fix
     the named conformance problems in the offending concept(s), then **re-run the Doctor directly** until
     it passes (exit 0): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>" --mode strict
     --format json`. Once it passes, remind the user to **`git add` the already-written merged `log.md` /
     regenerated `index.md`** (plus whatever was fixed) and finish the merge/commit — same as the `merged`
     branch. The Doctor wins — never hand-edit `index.md`/`log.md` to force it green.

Rollback: the merge only rewrites `log.md`/`index.md`, and the whole thing is a reviewable diff
recoverable via git. Defer conformance to the Doctor; never hand-edit the reserved files the engine owns.
