---
description: Check a bundle's OKF conformance with the Doctor (read-only).
argument-hint: "[bundle-or-file-path] [--json]"
allowed-tools: Bash(python3:*)
---

You are running `/llm-wiki:conform`. This is the user-facing surface of the Doctor. **Read-only — never
write or edit anything.**

Arguments: `$ARGUMENTS` may carry a target path (default `${CLAUDE_PROJECT_DIR}/llm-wiki`) and an optional
`--json` flag.

Steps:

1. Resolve the target path (default `${CLAUDE_PROJECT_DIR}/llm-wiki`).
2. Run the Doctor in strict-producer mode:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" <target> --mode strict --format text`
   (use `--format json` instead if the user passed `--json`).
3. Print the Doctor's output **verbatim**. Interpret the exit code for the user:
   - `0` → PASS (zero errors; warnings, if any, are advisory).
   - `1` → FAIL — list the reported violations and offer to fix them via `/llm-wiki:capture` /
     (Phase 2) refine, but do not modify anything now.
   - `2` → operational error — typically a bad path or a bare `index.md` (pass the bundle directory), but
     also any other usage error. Surface the message verbatim rather than assuming the cause.

Do not validate a bare `index.md` by itself — its root-vs-subdir rule needs bundle context; pass the
containing bundle directory instead.
