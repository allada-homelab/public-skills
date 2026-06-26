---
description: Refine an existing llm-wiki concept in place — edit its body/frontmatter, keeping indexes and the log correct.
argument-hint: "[concept path or title] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Bash(python3:*), Bash(date:*), Bash(cp:*), Bash(rm:*), Bash(mktemp:*), Bash(diff:*)
---

You are running `/llm-wiki:refine`. Edit **one** existing concept in place (same path — renames/moves
go through `/llm-wiki:reorganize`, removals through `/llm-wiki:prune`). Use the `wiki` skill for format
rules.

**Apply policy — auto by default.** Resolve the mode once with `python3
"${CLAUDE_PLUGIN_ROOT}/scripts/mode.py"`. In an **auto** mode (`proactive`/`max` — the default) apply
the gated edit directly: **no confirmation prompt and no prose recap**. Show the diff and wait for
approval **only** when the mode is `curated`, or when the user explicitly asks to review this edit. The
safety net on this path is the staged Doctor gate (blocking), the secret scan, and git-reversibility —
the apply lands via `cp`, so the PreToolUse guard floor (which covers *direct* bundle Write/Edit) does
**not** fire here. Auto-mode secret rule: if the secret scan flags a potential secret, **abort** — delete
the mirror, write nothing, and report the finding (auto mode has no human prompt to fall back on).

Arguments: `$ARGUMENTS` may carry a concept path/title and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root.** `--bundle` if given; else the configured bundle root — run `python3
   "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_path.py" resolve` (it honors a `bundle_path:` line in
   `.claude/llm-wiki(.local).md` else returns `${CLAUDE_PROJECT_DIR}/llm-wiki`) — if it holds a root
   `index.md` (`okf_version: "0.1"`); else walk up from the cwd. None → stop:
   "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Identify the target concept.** From the hint, Grep/Glob the bundle; on ambiguity, list candidates
   and ask. None found → suggest `/llm-wiki:capture`. Never guess.
3. **Compose the edit.** Read the concept and produce its full revised content: apply the user's change
   to body and/or frontmatter, **preserve a non-empty `type`**, keep links in the relative `./` form. Do
   not rename the file here. If the change alters a fact that the concept's `## Verify` anchor covers,
   update the anchor too and **re-stamp `verified:`** to now (a refine that re-confirms a fact is the
   point at which it was last verified). A `wiki-verifier` self-heal routes through this same gated apply.
4. **Stage in a mirror.** `mirror=$(mktemp -d)`; `cp -r "<bundle>/." "$mirror/"`. Write the revised
   concept into the mirror at its path, then regenerate indexes and append the log (capture the date
   once — `today=$(date -u +%F)` — and reuse `$today` in step 7 so a midnight rollover can't divert the
   apply to a different `## <date>` heading than the gate saw):
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" index "$mirror"` — rebuilds everything below
     the first `## ` heading from concept frontmatter (preamble above it preserved); flag in the diff any
     hand-written `## ` index section it would drop.
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Update --message "Refined [<title>](./<relpath>)." --date "$today"`
5. **Doctor gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format json`.
   Exit ≠ 0 → show violations verbatim, `rm -rf "$mirror"`, write nothing. Surface any `R4` link
   WARNINGs (report-only).
6. **Secret scan (always) + diff (when confirming).** Run `python3
   "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py" "$mirror/<relpath>" --format json` — **always**, since a
   hit halts an auto-apply (see the apply policy). When confirming (`curated`/on request), render hits as a
   prominent "⚠ Potential secrets — review before applying" block (never block) and show `diff -ru
   "<bundle>" "$mirror"`. In an auto mode skip the diff render and apply silently — but if a secret was
   flagged, **abort**: `rm -rf "$mirror"`, write nothing, and report the finding (no human prompt exists
   in auto mode).
7. **Apply.** In an auto mode, apply now without asking and **without a prose recap**. In `curated`/on
   request, apply only on approval; on decline, do nothing. Either way land *exactly the gated bytes* —
   copy the staged concept back (`cp "$mirror/<relpath>" "<bundle>/<relpath>"`); do **not** re-author it
   (LLM re-authoring drifts from what the gate approved). Then run the same `bundle_ops.py index` and
   `bundle_ops.py log-append … --date "$today"` against `<bundle>` (deterministic, same `$today`), and run
   the Doctor on the real bundle to confirm PASS. Clean up only a real mirror (`rm -rf "$mirror"` — never
   an unset path).

Defer all conformance judgments to the Doctor — if your draft and the Doctor disagree, the Doctor wins.
