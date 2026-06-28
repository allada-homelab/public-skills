#!/usr/bin/env python3
"""PreToolUse Doctor guard — block a bundle CONCEPT write that violates a per-file hard
rule (R1 parseable frontmatter, R2 non-empty `type`).

Scope is deliberately per-file: `index.md` / `log.md` are engine-owned and their rules
(R3*) are multi-file / context-dependent, so they stay in command orchestration, not this
per-call hook (per the Phase 3 plan). Only a full-content **Write** is validated — an
Edit/MultiEdit doesn't carry the whole resulting file, and the pre-existing file already
passed. (So an Edit/MultiEdit that *empties* a concept's `type:` is not caught here — that
conformance gap is deferred to the command-orchestration Doctor, not this hook.) This is a conformance guard,
not a security one, so it fails open on ambiguity — a guard must never wedge the session.
"""
import json
import os
import sys

from doctor import check_concept


def _under(path_abs, root_abs):
    try:
        return os.path.commonpath([root_abs, path_abs]) == root_abs
    except ValueError:
        return False


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if event.get("tool_name") != "Write":
        return 0
    tool_input = event.get("tool_input") or {}
    fp = tool_input.get("file_path")
    if not fp or not fp.endswith(".md") or os.path.basename(fp) in ("index.md", "log.md"):
        return 0  # not a concept file (reserved files are engine-owned)
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    bundle = os.path.realpath(os.path.join(project, "llm-wiki"))
    if not _under(os.path.realpath(fp), bundle):
        return 0

    findings = []
    check_concept(tool_input.get("content", ""), os.path.basename(fp), findings)
    errors = [f for f in findings if f["severity"] == "ERROR"]
    if errors:
        reason = "llm-wiki Doctor guard blocked this write: " + "; ".join(
            "%s — %s" % (f["rule"], f["message"]) for f in errors)
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
