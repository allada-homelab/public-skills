#!/usr/bin/env python3
"""PreToolUse secret guard — block a write that would land a credential in the bundle.

Reads the PreToolUse event JSON on stdin. If the target file is inside the llm-wiki
bundle (`$CLAUDE_PROJECT_DIR/llm-wiki`, symlinks resolved) and the text the tool would
introduce contains a likely secret (per `secret_scan.py`), **deny** the write with the
redacted findings as the reason. Writes outside the bundle pass through untouched. Runs on
every text-write path (Write/Edit), regardless of autonomy mode — this is the
floor that makes auto-capture safe.

Scope (deliberate): `Bash` redirection and `NotebookEdit` (`.ipynb`) are NOT covered — the
wiki is markdown concept files written via Write/Edit; scanning every Bash
command or notebook cell is out of scope.

Fail policy: a deny is emitted as the PreToolUse decision JSON; the script always exits 0
(the decision lives in the JSON, not the exit code). It fails *open* only when it cannot
identify an in-bundle target (unparseable event, no path, non-bundle path) — never wedging
unrelated writes. But once a write is confirmed in-bundle, it fails *closed*: if the
scanner itself errors, the write is denied rather than waved through unscanned.
"""
import json
import os
import sys

from secret_scan import scan


def _bundle_root(event):
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    # realpath resolves symlinks so a write reaching the bundle via a symlinked path
    # can't slip past the under-bundle check (it leaves a non-existent tail intact)
    return os.path.realpath(os.path.join(project, "llm-wiki"))


def _introduced_text(tool_name, tool_input):
    """The text this tool would add — all we can meaningfully scan pre-write."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("new_string", "")
    return ""


def _under(path_abs, root_abs):
    try:
        return os.path.commonpath([root_abs, path_abs]) == root_abs
    except ValueError:
        return False  # different drives / unrelated roots


def _deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0  # can't identify a target → fail open (never wedge unrelated writes)
    tool_input = event.get("tool_input") or {}
    fp = tool_input.get("file_path")
    if not fp:
        return 0
    fp_abs = os.path.realpath(fp)
    if not _under(fp_abs, _bundle_root(event)):
        return 0  # not a bundle write — not our concern

    # confirmed in-bundle: from here we fail CLOSED — a scanner error denies, not allows
    try:
        findings = scan(_introduced_text(event.get("tool_name", ""), tool_input))
    except Exception as e:  # noqa: BLE001 — a security floor must not wave a write through on its own bug
        _deny("llm-wiki secret guard could not scan this in-bundle write (%s); failing closed — "
              "retry, or write outside the bundle." % type(e).__name__)
        return 0
    if findings:
        detail = "; ".join("%s (%s)" % (f["category"], f["preview"]) for f in findings)
        _deny("llm-wiki secret guard blocked this write — %d potential secret(s): %s. "
              "Remove or redact the credential before writing." % (len(findings), detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
