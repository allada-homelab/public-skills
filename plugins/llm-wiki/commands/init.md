---
description: Bootstrap an empty, OKF v0.1-conformant llm-wiki bundle (one-time).
argument-hint: "[target-path]"
allowed-tools: Glob, Read, Write, Bash(python3:*)
---

You are running `/llm-wiki:init`. Create a new, conformant OKF v0.1 bundle. Use the `wiki` skill for
the format rules. **Confirm-first: write nothing until the user approves the shown content.**

Target directory: `$ARGUMENTS` if given, else `${CLAUDE_PROJECT_DIR}`.

Steps:

1. **Refuse if a bundle already exists.** Glob the target for `index.md`. If a root `index.md` exists
   (frontmatter `okf_version: "0.1"`), stop: "A bundle already exists here — use `/llm-wiki:capture`."
2. **Offer an optional domain pack.** Ask whether to seed a starter subdirectory (e.g. an engineering
   pack with an empty `runbooks/`, `decisions/` and their no-frontmatter `index.md`). Default: none.
   Packs are suggestions, never required.
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
5. **Show & confirm.** Display the full content of every file to be created. On explicit approval,
   Write them — **root `index.md` first**; if any write fails, stop and report exactly what landed
   (no partial-bundle cleanup magic — fail loud).
6. Report the bundle path and suggest `/llm-wiki:capture` to add the first concept.

Use relative `./` links throughout. Never invent OKF rules — defer to the `wiki` skill and the Doctor.
