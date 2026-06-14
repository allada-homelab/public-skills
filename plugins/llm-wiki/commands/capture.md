---
description: Capture a finding from the current work as one conformant OKF concept (the core loop).
argument-hint: "[title or finding hint] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Edit, Bash(python3:*)
---

You are running `/llm-wiki:capture`. Turn a finding from the current session into **one** conformant
OKF concept at the **bundle root** (Phase 1 does not create subdirectories). Use the `okf` skill for
format rules and `references/concept-template.md` for the skeleton. **Confirm-first: write nothing
until the user approves the diff.**

Arguments: `$ARGUMENTS` may carry a title/finding hint and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root.** Use `--bundle` if given, else walk up from `${CLAUDE_PROJECT_DIR}` for
   a root `index.md` (`okf_version: "0.1"`). None found → stop: "No OKF bundle here. Run
   `/llm-wiki:init` first."
2. **Decide the concept.** From the hint and session context, determine `type`, `title`, and a
   root-level slug (`<slug>.md`). If the subject is unclear, ask before proceeding.
3. **Duplicate check.** Grep the bundle for the title / slug / any `resource`, and Glob the path. On a
   strong match, **refuse**: name the existing concept and offer to refine it later (refine is Phase 2).
   Write nothing.
4. **Compose three pending artifacts:**
   - the new concept (from the template; relative `./` links; a non-empty `type`);
   - the regenerated **root** `index.md` (full deterministic rewrite — add this concept's bullet,
     preserve every existing sibling row you cannot confidently re-derive; only change a sibling row if
     that sibling's frontmatter actually changed);
   - an appended `log.md` **Creation** entry under today's `## YYYY-MM-DD` (UTC), newest-first.
   - **Cross-link:** link to a related existing concept only if one exists; on the first capture into an
     empty bundle, add no cross-link and say so in the diff.
5. **Report-only link check.** Resolve the new concept's outbound links against the staged bundle;
   surface any dangling link in the confirm diff as a WARNING (do not block).
6. **Doctor gate (bundle mode).** Stage the new concept + regenerated index + appended log into a
   temporary mirror reproducing their bundle-relative paths, then run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" <tmp-mirror> --mode strict --format json`.
   Exit ≠ 0 → show violations verbatim, write nothing, delete the mirror.
7. **Secret scan (report-only).** Run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" <pending-concept> --format json` (and over
   the log bullet). Render any findings as a prominent "⚠ Potential secrets detected — review before
   confirming" block in the diff. **Never block** on secrets in Phase 1.
8. **Show & confirm.** Full content for the new concept; unified diffs for the regenerated index and the
   log append; the secret block and any dangling-link warning. On approval, write in order:
   concept → index → log (`Edit` the log append). If a later write fails, report exactly which landed.
   On decline, do nothing (clean no-op).
9. **Consultation counter (optional, confirm-gated).** Not incremented by capture.

Defer all conformance judgments to the Doctor — if your draft and the Doctor disagree, the Doctor wins.
