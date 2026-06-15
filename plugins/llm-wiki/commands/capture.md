---
description: Capture a finding from the current work as one conformant OKF concept (the core loop).
argument-hint: "[title or finding hint] [--into <subdir>] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Edit, Bash(python3:*), Bash(cp:*), Bash(rm:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:capture`. Turn a finding from the current session into **one** conformant
OKF concept — at the **bundle root by default**, or in a **subdirectory when there is a clear reason**
(see "Decide placement" below). Use the `wiki` skill for format rules and
`references/concept-template.md` for the skeleton. **Confirm-first: write nothing to the real bundle
until the user approves the diff.**

Arguments: `$ARGUMENTS` may carry a title/finding hint, an optional `--into <subdir>` (force a target
directory, creating it if needed), and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root.** Use `--bundle` if given; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`
   if it holds a root `index.md` (`okf_version: "0.1"`); else walk up from the cwd for one. None found →
   stop: "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Decide the concept.** From the hint and session context, determine `type`, `title`, and a slug
   (`<slug>.md`). If the subject is unclear, ask before proceeding.
3. **Decide placement (default root).** Choose the target directory for `<slug>.md`:
   - If `--into <subdir>` was given, use it — validate it stays inside the bundle (no `../` escape, no
     reserved names), creating intermediate dirs.
   - Otherwise **default to the bundle root**, and choose a subdirectory *only* when you can name a real
     reason:
     - ✅ it clearly **joins an existing section** (a subdir it belongs to);
     - ✅ it **joins/forms a cluster** — there are already ~3+ sibling concepts on the same sub-topic that
       should become a section (consider `/llm-wiki:reorganize` for the existing ones);
     - ✅ it is a **distinct domain/subsystem** with its own identity and expected growth.
   - Do **not** create a brand-new subdirectory for a single concept ("lonely folder"), fold by type with
     thin contents, or nest speculatively (prefer depth 1; rarely 2). When in doubt, root. The Doctor
     emits a **WARNING (R5)** for a subdir holding a single lonely concept — that is the backstop here.
4. **Duplicate check.** Grep the bundle for the title / slug / any `resource`, and Glob the path. On a
   strong match, **refuse**: name the existing concept and offer `/llm-wiki:refine`. Write nothing.
5. **Compose the concept.** From the template; relative `./` links; a non-empty `type`. Cross-link to a
   related existing concept only if one exists; on the first capture into an empty bundle, add no
   cross-link and say so in the diff.
6. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`. Write the new concept
   into the mirror at `<target-dir>/<slug>.md` (creating intermediate dirs), then regenerate indexes and
   append the log (one UTC date, reused in step 9):
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Creation --message "Added [<title>](./<relpath>)." --date <today>`
7. **Doctor gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format json`.
   Exit ≠ 0 → show violations verbatim, `rm -rf "$mirror"`, write nothing. Surface any `R4` (link) or
   `R5` (lonely-subdir) **WARNINGs** — report-only, they never block; an R5 on your placement is a cue to
   reconsider nesting.
8. **Secret scan + diff.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" "$mirror/<relpath>"
   --format json` (and over the log bullet); render hits as a prominent "⚠ Potential secrets — review
   before confirming" block (**never block** in Phase 1). Show `diff -ru "<bundle>" "$mirror"`, and state
   the **placement + reason** (e.g. "→ `backend/` — joining the existing Backend section", or "→ root — no
   section warrants it yet").
9. **Confirm & apply.** On approval, land *exactly the gated bytes* — copy the staged concept back
   (`cp "$mirror/<relpath>" "<bundle>/<relpath>"`, creating intermediate dirs); do **not** re-author it
   (re-authoring drifts from what the user approved). Then run the same `bundle_ops.py index` and
   `bundle_ops.py log-append … --date <today>` against `<bundle>` (deterministic), and run the Doctor on
   the real bundle to confirm PASS. If a write fails, report exactly what landed. On decline, do nothing
   (clean no-op). Clean up only a real mirror (`rm -rf "$mirror"` — never an unset path).

Defer all conformance judgments to the Doctor — if your draft and the Doctor disagree, the Doctor wins.
