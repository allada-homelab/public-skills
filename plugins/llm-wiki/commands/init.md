---
description: Bootstrap an empty, OKF v0.1-conformant llm-wiki bundle (one-time).
argument-hint: "[target-path]"
allowed-tools: Glob, Read, Write, Edit, AskUserQuestion, Bash(python3:*), Bash(mktemp:*), Bash(rm:*), Bash(git:*), Bash(grep:*)
---

You are running `/llm-wiki:init`. Create a new, conformant OKF v0.1 bundle. Use the `wiki` skill for
the format rules.

**Apply policy — auto by default.** Resolve the mode once with `python3
"${CLAUDE_PLUGIN_ROOT}/scripts/mode.py"`. In an **auto** mode (`proactive`/`max` — the default) create
the gated bundle directly: no confirmation prompt and no domain-pack question (default: no pack). Show
the files for approval — and offer the optional pack — only in `curated` mode or when the user explicitly
asks. (The location/tracking prompts in step 0 are input-gathering, not write-approval — they are asked
regardless of mode when the location is unspecified.)

Steps:

0. **Resolve (and, if relocating, persist) the creation target.** Precedence:
   1. `$ARGUMENTS` (a positional path) or `--bundle <path>` if given → use it.
   2. Else if a location is already configured — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_path.py"
      resolve` returns a **non-default** path — use it silently, and print one line so relocation stays
      discoverable: *"llm-wiki configured to `<path>`; pass a path (e.g. `/llm-wiki:init .agent-context`)
      to change it."*
   3. Else **ask** (`AskUserQuestion`):
      - **(a) Location** — `llm-wiki/` **(Recommended)**, the default; `.agent-context/`; *Other* →
        free-text (repo-relative, `~/…`, or absolute).
      - **(b) Tracking** — a single 4-option question, asked **only when (a) is non-default *and*
        repo-relative**. Each option maps to a fixed outcome:
        | Choice | Config file written | Ignore action |
        |--------|--------------------|---------------|
        | Shared with team | committed `.claude/llm-wiki.md` (`--shared`) | none (commit the bundle too; remind to `git add`) |
        | **Just me, keep out of the shared repo (Recommended)** | `.claude/llm-wiki.local.md` | append the path to `.git/info/exclude` |
        | Each person keeps their own here | `.claude/llm-wiki.local.md` | append the path to committed `.gitignore` |
        | Just my config; I'll commit the concepts | `.claude/llm-wiki.local.md` | none |

        **Skip (b) and force single-user** (write `.local.md`, no ignore action) when the chosen path is
        `~`/absolute — a machine-specific path can't be shared and isn't in this repo to ignore; say why.
   **Persist a non-default choice** with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_path.py" set
   <value> [--shared]` (it refuses an unsafe value — root-collapse, or a non-repo-relative `--shared`
   value — and preserves any `mode:` line). A choice of the default `llm-wiki/` writes **no** config.
   For an ignore action, **idempotently** append the bundle path (skip if already present — `grep` first)
   to the file from `git rev-parse --git-path info/exclude`, or to `.gitignore`.
   Treat the resolved target as `<target>` below.

1. **Relocation guard — never silently orphan.** If `<target>` differs from a location that already
   holds a bundle — glob the *previously-resolved* location (the prior configured path, else
   `${CLAUDE_PROJECT_DIR}/llm-wiki`) for a root `index.md` — ask (`AskUserQuestion`) before proceeding:
   **Cancel** (default — write nothing, create nothing), **Keep both** (proceed; warn loudly naming
   **both** paths; the old bundle stays put and unmanaged), or **Move** (a true bundle-root move isn't
   built yet → falls back to *Keep both* plus a note to move the old concepts manually).

2. **Refuse if a bundle already exists at the target.** Glob `<target>` for `index.md`. If a root
   `index.md` exists (frontmatter `okf_version: "0.1"`), stop: "A bundle already exists at `<target>` —
   use `/llm-wiki:capture`."
3. **Optional domain pack.** A starter subdirectory (e.g. an engineering pack with an empty `runbooks/`,
   `decisions/` and their no-frontmatter `index.md`) is available; **default: none**. In `curated`/on
   request, ask whether to seed one; in an auto mode, skip it (none) unless the user named a pack. Packs
   are suggestions, never required.
4. **Compose the file set in memory:**
   - `<target>/index.md` — frontmatter **exactly** `okf_version: "0.1"`, then a short heading and an
     (initially empty) bullet list.
   - `<target>/log.md` — `# Directory Update Log`, then today's `## YYYY-MM-DD` heading and
     `* **Initialization**: Bundle created.` (UTC date).
   - any chosen pack subdir `index.md` files (zero frontmatter).
5. **Doctor gate (bundle mode).** Stage the composed files into a temporary mirror directory that
   reproduces their bundle-relative paths, then run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" <tmp-mirror> --mode strict --format json`.
   If exit code ≠ 0, show the violations verbatim and stop — write nothing. Delete the mirror.
6. **Apply.** In an auto mode, Write the gated files directly (no recap); in `curated`/on request,
   display the full content of every file and Write only on explicit approval. Either way **root
   `index.md` first**; if any write fails, stop and report exactly what landed (no partial-bundle cleanup
   magic — fail loud).
7. Report the bundle path and suggest `/llm-wiki:capture` to add the first concept.

Use relative `./` links throughout. Never invent OKF rules — defer to the `wiki` skill and the Doctor.
