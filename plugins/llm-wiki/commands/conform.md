---
description: Run the OKF Doctor over a bundle and report conformance (read-only).
argument-hint: "[bundle-or-file-path] [--json]"
allowed-tools: Glob, Read, Bash(python3:*)
---

You are running `/llm-wiki:conform`. This is the user-facing surface of the Doctor. **Read-only — never
write or edit anything.**

Arguments: `$ARGUMENTS` may carry a target path (default `${CLAUDE_PROJECT_DIR}`) and an optional
`--json` flag.

Steps:

1. Resolve the target path (default `${CLAUDE_PROJECT_DIR}`).
2. Run the Doctor in strict-producer mode:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" <target> --mode strict --format text`
   (use `--format json` instead if the user passed `--json`).
3. Print the Doctor's output **verbatim**. Interpret the exit code for the user:
   - `0` → PASS (zero errors; warnings, if any, are advisory).
   - `1` → FAIL — list the reported violations and offer to fix them via `/llm-wiki:capture` /
     (Phase 2) refine, but do not modify anything now.
   - `2` → operational error (bad path, or a bare `index.md` was passed — pass the bundle directory).
     Surface the message verbatim.

Do not validate a bare `index.md` by itself — its root-vs-subdir rule needs bundle context; pass the
containing bundle directory instead.
