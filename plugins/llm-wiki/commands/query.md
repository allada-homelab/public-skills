---
description: Answer a wiki question with cited sources (updates a consult counter).
argument-hint: "<question> [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Bash(python3:*), Bash(git:*), Task
---

You are running `/llm-wiki:query`. Answer the user's question from concepts you actually read, with
citations, and **trust-but-verify** what the answer relies on (step 5). Use the `wiki` skill for the
format (see its "Reading is trust-but-verify" + "Verify anchors" sections). The bundle stays read-only
here: query itself never writes a concept — it may run a read-only `git` freshness check and dispatch a
background `wiki-verifier` (which owns any self-heal), plus the optional consultation-counter write.

Arguments: `$ARGUMENTS` is the question (**required** — if empty, ask for it; never guess). It may also
carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk
   up from the cwd for a root `index.md`). None → "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Find entry points.** Grep key terms from the question and read the root `index.md`. Traverse
   minimally, following only cross-links that bear on the question. A concept "counts" only when you
   actually `Read` its body (index files don't count).
3. **Answer from read content, trusted on its face.** Ground every claim in a concept; cite each by its
   bundle-relative path / title. End with a `Sources:` list. Do **not** fabricate or fill gaps from
   general knowledge. Trust concepts as a curated summary — a verification read against a concept's
   `## Verify` anchor (step 5) is the sanctioned confirm step, **not** "filling from general knowledge."
4. **Gap flag (required).** If no concept answers, say "The wiki does not contain an answer to this,"
   and emit a structured line:
   `GAP: <question> — no concept covers <topic>. Consider /llm-wiki:capture to add it.`
   A query can be partly answered and partly a gap — report both. Phase 1 only *reports* gaps.
5. **Trust-but-verify (non-blocking).** The answer above stands now — do **not** block on verification.
   Then, for each concept a **load-bearing** claim rests on (tie "load-bearing" to the question's intent —
   a step about to be run, a value about to change — not every cited claim):
   - **Freshness gate (cheap, sync).** If the concept has a `## Verify` anchor + `verified:` stamp and the
     project is a git repo, check whether any anchored file changed since the stamp — let git do the date
     math (handles timezones): `git -C "${CLAUDE_PROJECT_DIR}" log --since="<verified>" -1 --format=%H --
     <anchor-file>` (this freshness gate is shared with `/llm-wiki:tend` step 4a — keep the two
     byte-identical). **Empty (no commit since) → trust, do nothing.** No anchor / not a git repo /
     unresolvable here → label the claim **couldn't-verify** (and flag a missing/weak anchor as a curation
     gap); never refuse, never auto-edit.
   - **Changed → dispatch a background verifier.** Spawn the `wiki-verifier` subagent (Task tool, Sonnet)
     for that concept and **finish the turn**; note in the answer that the claim is being verified in the
     background (a `STALE:` correction may follow). At most **one verifier per concept per turn** (dedupe).
   - **Inline escalation** *only* when the claim is high-stakes for an action about to be taken, or its
     anchor is a quick `run:` one-liner (cheaper than spawning): confirm inline and report **confirmed**,
     or `STALE: <concept> — wiki says X; current state shows Y` + propose `/llm-wiki:refine <concept>`.
   - **Lightweight, always:** check the named anchor and *only* that — a weak/missing anchor is a curation
     signal, never license to re-investigate.
6. **Consultation counter (auto by default).** Track which concepts were consulted this turn, then apply
   the shared counter procedure below.
   _Counter procedure (keep byte-identical with `/llm-wiki:explore` step 4; ideal home
   `skills/wiki/references/consultation-counter.md` once that path is editable):_ resolve the mode once
   with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mode.py"` (an auto mode is the default). Increment each
   consulted concept's count in `<bundle-root>/.llm-wiki/consultations.json` (create it as `{}` if absent;
   this dotfile is invisible to the Doctor and to OKF consumers). In an auto mode write the increments
   silently; in `curated`/on request, propose them first and write only on approval (if declined, results
   stand and the counter is untouched). If the file is corrupt or missing, treat it as `{}` — never let
   counter bookkeeping break the command.
