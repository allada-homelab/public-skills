---
description: Answer a wiki question with cited sources, or browse the wiki from a starting point (read-only).
argument-hint: "<question | start-subpath> [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Bash(git:*), Task
---

You are running `/llm-wiki:query`. This command **reads** the wiki two ways — pick by what the user asked:

- **Answer mode** (a question): answer from concepts you actually read, with citations, and
  **trust-but-verify** what the answer relies on (step 5).
- **Browse mode** (a starting point, or "explore/browse the wiki"): navigate by **progressive
  disclosure** — read `index.md` listings and follow links from a starting point, not every file.

Use the `wiki` skill for the format (see its "Reading is trust-but-verify" + "Verify anchors" sections).
The bundle stays **read-only** here: query never writes a concept — it may run a read-only `git` freshness
check and dispatch a background `wiki-verifier` (which owns any self-heal).

Arguments: `$ARGUMENTS` is the question or the start subpath. It may also carry `--bundle <path>`. If it
is empty, default to **browse mode** from the bundle root.

Steps:

1. **Resolve the bundle root** (`--bundle`; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk
   up from the cwd for a root `index.md`). **None → there is no wiki yet** (one is created automatically on
   the first `/llm-wiki:capture`); say the wiki is empty and stop.

2. **Pick the mode** from `$ARGUMENTS`: a natural-language question → **answer mode** (steps 3–5); a
   start subpath, a directory, or an explicit browse/explore request (or empty) → **browse mode** (step 6).

### Answer mode

3. **Find entry points.** Grep key terms from the question and read the root `index.md`. Traverse
   minimally, following only cross-links that bear on the question. A concept "counts" only when you
   actually `Read` its body (index files don't count).
4. **Answer from read content, trusted on its face.** Ground every claim in a concept; cite each by its
   bundle-relative path / title. End with a `Sources:` list. Do **not** fabricate or fill gaps from
   general knowledge. Trust concepts as a curated summary — a verification read against a concept's
   `## Verify` anchor (step 5) is the sanctioned confirm step, **not** "filling from general knowledge."
   **Gap flag (required).** If no concept answers, say "The wiki does not contain an answer to this," and
   emit a structured line:
   `GAP: <question> — no concept covers <topic>. Consider /llm-wiki:capture to add it.`
   A query can be partly answered and partly a gap — report both.
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
     or `STALE: <concept> — wiki says X; current state shows Y` + propose `/llm-wiki:capture <concept>` to
     correct it.
   - **Lightweight, always:** check the named anchor and *only* that — a weak/missing anchor is a curation
     signal, never license to re-investigate.

### Browse mode

6. **Read the starting `index.md`** (the bundle root, or the given subpath) and present its bullets —
   titles + descriptions only, **not** full bodies (this is the lean-context win). If an `index.md` is
   missing at a level, fall back to a Glob listing of `*.md` and continue — never abort (tolerant
   consumer). Then **follow the user's pick:** a subdirectory → recurse into its `index.md`; a concept →
   `Read` and present it. A broken link → note it inline and keep going. Do not modify any concept,
   `index.md`, or `log.md` — browsing is for reading.
