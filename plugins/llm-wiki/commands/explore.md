---
description: Navigate the llm-wiki via index.md progressive disclosure. Read-only except a consultation-counter update (silent in an auto mode; confirm-gated in curated).
argument-hint: "[start-subpath] [--bundle <path>]"
allowed-tools: Glob, Read, Write
---

You are running `/llm-wiki:explore`. Help the user navigate the bundle by **progressive disclosure** —
read `index.md` listings, not every file. Use the `wiki` skill for the format. Read-only except the
consultation-counter write (silent in an auto mode; confirm-gated in `curated`).

Arguments: `$ARGUMENTS` may carry a start subpath (default: bundle root) and `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`; else walk
   up from the cwd for a root `index.md`). None → "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Read the starting `index.md`** and present its bullets — titles + descriptions only, **not** full
   bodies (this is the lean-context win). If an `index.md` is missing at a level, fall back to a Glob
   listing of `*.md` and continue — never abort (tolerant consumer).
3. **Follow the user's pick:** a subdirectory → recurse into its `index.md`; a concept → `Read` and
   present it (this concept now counts as consulted). A broken link → note it inline and keep going.
4. **Consultation counter (auto by default).** Track which concepts were opened this run. Before
   finishing, increment each opened concept's count in `<bundle-root>/.llm-wiki/consultations.json`
   (create it as `{}` if absent; this dotfile is invisible to the Doctor and to OKF consumers). Resolve
   the mode by reading `.claude/llm-wiki.local.md` (treat it as `curated` only if it contains a
   `mode: curated` line; absent or any other value → an auto mode, the default): in an auto mode write the
   increments silently; in `curated`/on request, propose them first and write only on approval (if
   declined, results stand and the counter is untouched). If the file is corrupt or missing, treat it as
   `{}` — never let counter bookkeeping break navigation.

Do not modify any concept, `index.md`, or `log.md` — explore is for reading.
