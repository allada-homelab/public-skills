---
description: Reorganize the llm-wiki — move/rename concepts (incl. into subdirectories), rewriting every link with zero breakage.
argument-hint: "[what to reorganize] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Edit, Bash(python3:*), Bash(cp:*), Bash(rm:*), Bash(rmdir:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:reorganize`. Move and/or rename one or more concepts — including into **new
subdirectories** — while keeping every link valid. This is the highest-blast command; the gate is a
link-health **pre/post diff**: the operation must introduce **zero** newly-broken links. Use the `wiki`
skill for format rules. **Confirm-first: write nothing to the real bundle until the user approves.**

Arguments: `$ARGUMENTS` may describe the reorganization and carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up).
   None → stop: "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Plan the moves.** From the request, produce an explicit list of `from → to` bundle-relative paths
   (a rename is a move within the same directory; a new subdirectory is created by its `to` path). Show
   the plan and confirm the shape before staging if it is non-trivial.
3. **Baseline link health.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>" --mode
   strict --format json` and record the **set of already-broken links** (`before`). Identify each broken
   link by its **resolved target** (resolve the link relative to its containing file, or from the bundle
   root for `/…` links) — **not** the raw link string, which legitimately changes when a file moves. A
   conformant bundle has an empty `before`.
4. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`. For each planned move,
   in order: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" move "$mirror" --from <a> --to <b>`
   (this rewrites inbound links in **both** the `./` and `/` forms and the moved file's own relative
   links). Then regenerate indexes (creating zero-frontmatter subdir `index.md` files and refreshing the
   root) and append the log, reusing one UTC date in step 7:
   - If a move **empties a source subdirectory** (the index generator only refreshes *live* dirs, so a
     stale subdir index would otherwise linger): only when the directory contains **nothing but
     `index.md`** and is **not the bundle root**, `rm` that `index.md` then `rmdir` the directory
     (`rmdir`, not `rm -rf`, so a still-occupied dir fails loud rather than deleting real content).
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Update --message "Moved <summary>." --date <today>`
5. **Doctor gate + link-health diff.** Run the Doctor on `$mirror` (strict, json). Exit ≠ 0 → show, `rm
   -rf "$mirror"`, stop. Collect the mirror's broken links by **resolved target** (`after`, same keying
   as step 3). Require `after ⊆ before`: if any link broke that wasn't already broken (the common case:
   `before` is empty, so `after` must be empty too), it is a **regression** — report each newly-broken
   link, `rm -rf "$mirror"`, write nothing.
6. **Secret scan + diff.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" <path> --format
   json` over each concept whose content changed; render hits as a "⚠ Potential secrets" block (never
   block). Show `diff -ru "<bundle>" "$mirror"`.
7. **Confirm & apply.** On approval, reproduce on the real bundle — the moves are deterministic, so
   re-run the same `move`(s) in order → emptied-dir cleanup (step 4) → `index` → `log-append … --date
   <today>` against `<bundle>`, then run the Doctor on the real bundle and re-check `after ⊆ before`. On
   decline, do nothing. Clean up only a real mirror (`rm -rf "$mirror"` — never an unset path).

Rollback: the whole reorganization is one reviewable diff, recoverable via git. Defer conformance to the
Doctor; never hand-edit links the `move` engine owns.
