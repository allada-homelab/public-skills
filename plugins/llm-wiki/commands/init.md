---
description: Bootstrap an empty, OKF-conformant wiki bundle (one-time).
argument-hint: "[target-path]"
allowed-tools: Glob, Read, Write, Bash(python3:*), Bash(mktemp:*), Bash(cp:*), Bash(rm:*)
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
   - any chosen pack subdir `index.md` files (zero frontmatter).
   `log.md` is **not** hand-authored — `bundle_ops log-append` generates it (with the correct UTC date)
   in step 4.
4. **Stage + Doctor gate (bundle mode).** Stage the composed files into a temporary mirror
   (`mirror=$(mktemp -d)`) that reproduces their bundle-relative paths, then generate the log with the
   deterministic engine (it computes the UTC date itself — no `date` call needed):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" log-append "$mirror" --kind Initialization --message "Bundle created."`.
   Then gate: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" "$mirror" --mode strict --format json`.
   If exit code ≠ 0, show the violations verbatim, `rm -rf "$mirror"`, and stop — write nothing.
5. **Apply.** Land *exactly the gated bytes* — `cp` each staged file from the mirror to its
   `<target>/<relpath>` (creating the target dir; **root `index.md` first**). In an auto mode do this
   directly (no recap); in `curated`/on request, display the full content of every file and copy only on
   explicit approval. If any write fails, stop and report exactly what landed (no partial-bundle cleanup
   magic — fail loud). Clean up the mirror (`rm -rf "$mirror"`).
6. Report the bundle path and suggest `/llm-wiki:capture` to add the first concept.

Use relative `./` links throughout. Never invent OKF rules — defer to the `wiki` skill and the Doctor.
