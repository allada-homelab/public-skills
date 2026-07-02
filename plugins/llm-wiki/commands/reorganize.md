---
description: Move/rename concepts, rewriting every link with zero breakage.
argument-hint: "[what to reorganize] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(python3:*), Bash(date:*), Bash(cp:*), Bash(rm:*), Bash(rmdir:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:reorganize`. Move and/or rename one or more concepts — including into **new
subdirectories** — while keeping every link valid. This is the highest-blast command; the gate is a
link-health **pre/post diff**: the operation must introduce **zero** newly-broken links. Use the `wiki`
skill for format rules.

**Writes always apply directly.** There is no confirm-first path: stage the moves on a mirror, gate them,
and apply — **no confirmation prompt and no prose recap**. The safety net is the link-health pre/post gate
(`after ⊆ before`), the Doctor gate (blocking), the secret scan, and git-reversibility. Secret rule: if
the secret scan flags a potential secret, **abort** — delete the mirror, write nothing, and report the
finding.

Arguments: `$ARGUMENTS` may describe the reorganization and carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk up).
   None → stop: there is no wiki here yet (one is created automatically on the first `/llm-wiki:capture`),
   so there is nothing to reorganize.
2. **Plan the moves.** From the request, produce an explicit list of `from → to` bundle-relative paths
   (a rename is a move within the same directory; a new subdirectory is created by its `to` path).
   Proceed without confirming the plan.
3. **Baseline link health.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>" --mode
   strict --format json` and record the **set of already-broken links** (`before`). Identify each broken
   link by its **resolved target** (resolve the link relative to its containing file, or from the bundle
   root for `/…` links) — **not** the raw link string, which legitimately changes when a file moves. The
   Doctor's `R4` finding carries only the **raw link string and its containing `file:line`** (there is no
   resolved-target field in the output), so you must compute the target yourself —
   `normpath(join(dirname(file), rawlink))`, or from the bundle root for a leading-`/` link — and key
   both `before` and `after` on that. A bundle with no pre-existing broken links has an empty `before`;
   conformance does **not** guarantee this, since R4 broken links are tolerated WARNINGs. If this baseline
   Doctor reports **errors** (R1/R2/R3 — not R4 warnings), the bundle is non-conformant: stop and fix it
   first (run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "<bundle>"` to see the violations), since
   the step-5 gate would otherwise block on those same errors and surface them as the blocker.
4. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`. For each planned move,
   in order: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" move "$mirror" --from <a> --to <b>`
   (this rewrites inbound links in **both** the `./` and `/` forms and the moved file's own relative
   links). Then regenerate indexes (creating zero-frontmatter subdir `index.md` files and refreshing the
   root) and append the log (capture the date once — `today=$(date -u +%F)` — and reuse `$today` in step 7):
   - If a move **empties a source subdirectory** (the index generator only refreshes *live* dirs, so a
     stale subdir index would otherwise linger): only when the directory contains **nothing but
     `index.md`** and is **not the bundle root**, `rm` that `index.md` then `rmdir` the directory
     (`rmdir`, not `rm -rf`, so a still-occupied dir fails loud rather than deleting real content).
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Update --message "Moved <summary>." --date "$today"`
5. **Doctor gate + link-health diff.** Run the Doctor on `$mirror` (strict, json). Exit ≠ 0 → show, `rm
   -rf "$mirror"`, stop. Collect the mirror's broken links by **resolved target** (`after`, same keying
   as step 3). Require `after ⊆ before`: if any link broke that wasn't already broken (the common case:
   `before` is empty, so `after` must be empty too), it is a **regression** — report each newly-broken
   link, `rm -rf "$mirror"`, write nothing.
6. **Secret scan (always).** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" <path> --format
   json` over each concept whose content changed (and over the staged log bullet) — **always**, since a hit
   halts the apply. A **hit** is a non-zero `summary.findings` in the JSON output (`secret_scan.py` always
   exits 0, so never key the abort off `$?`). On any hit, **abort**: `rm -rf "$mirror"`, write nothing, and
   report the finding.
7. **Apply.** Apply now without asking and **without a prose recap**. Reproduce on the real bundle — the
   moves are deterministic, so re-run the same `move`(s) in order → emptied-dir cleanup (step 4) → `index`
   → `log-append … --date "$today"` against `<bundle>`, then run the Doctor on the real bundle and re-check
   `after ⊆ before`. If a write/step fails, report exactly what landed. Clean up only a real mirror (`rm
   -rf "$mirror"` — never an unset path).

Rollback: the whole reorganization is one reviewable diff, recoverable via git. Defer conformance to the
Doctor; never hand-edit links the `move` engine owns.
