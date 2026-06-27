---
description: Bootstrap an empty, OKF v0.1-conformant llm-wiki bundle (one-time).
argument-hint: "[target-path]"
allowed-tools: Glob, Read, Write, Bash(python3:*), Bash(mktemp:*), Bash(rm:*)
---

You are running `/llm-wiki:init`. Create a new, conformant OKF v0.1 bundle. Use the `wiki` skill for
the format rules.

**Apply policy — auto by default.** Resolve the mode once with `python3
"${CLAUDE_PLUGIN_ROOT}/scripts/mode.py"`. In an **auto** mode (`proactive`/`max` — the default) create
the gated bundle directly: no confirmation prompt and no domain-pack question (default: no pack). Show
the files for approval — and offer the optional pack — only in `curated` mode or when the user explicitly
asks.

Target directory: `$ARGUMENTS` if given, else the default bundle location `${CLAUDE_PROJECT_DIR}/llm-wiki`.

Steps:

1. **Refuse if a bundle already exists.** Glob the target for `index.md`. If a root `index.md` exists
   (frontmatter `okf_version: "0.1"`), stop: "A bundle already exists here — use `/llm-wiki:capture`."
2. **Optional domain pack.** A starter subdirectory (e.g. an engineering pack with an empty `runbooks/`,
   `decisions/` and their no-frontmatter `index.md`) is available; **default: none**. In `curated`/on
   request, ask whether to seed one; in an auto mode, skip it (none) unless the user named a pack. Packs
   are suggestions, never required.
3. **Compose the file set in memory:**
   - `<target>/index.md` — frontmatter **exactly** `okf_version: "0.1"`, then a short heading and an
     (initially empty) bullet list.
   - `<target>/log.md` — `# Directory Update Log`, then today's `## YYYY-MM-DD` heading and
     `* **Initialization**: Bundle created.` (UTC date).
   - any chosen pack subdir `index.md` files (zero frontmatter).
4. **Doctor gate (bundle mode).** Stage the composed files into a temporary mirror directory that
   reproduces their bundle-relative paths, then run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" <tmp-mirror> --mode strict --format json`.
   If exit code ≠ 0, show the violations verbatim and stop — write nothing. Delete the mirror.
5. **Apply.** In an auto mode, Write the gated files directly (no recap); in `curated`/on request,
   display the full content of every file and Write only on explicit approval. Either way **root
   `index.md` first**; if any write fails, stop and report exactly what landed (no partial-bundle cleanup
   magic — fail loud).
6. Report the bundle path and suggest `/llm-wiki:capture` to add the first concept.

Use relative `./` links throughout. Never invent OKF rules — defer to the `wiki` skill and the Doctor.
