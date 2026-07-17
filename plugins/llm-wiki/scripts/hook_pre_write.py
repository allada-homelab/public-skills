#!/usr/bin/env python3
"""PreToolUse write guard — the merged secret + Doctor conformance floor for bundle writes.

Formerly two separate PreToolUse hooks (a secret guard + a Doctor conformance guard), each of
which parsed the event and spawned its own interpreter on every Write/Edit. They are
merged here into a single entrypoint: one event parse, one `file_path` extraction, one
bundle-containment check, then both checks in sequence — one interpreter spawn per edit, not two.

Two checks, in precedence order, for a write that lands inside the llm-wiki bundle
(`$CLAUDE_PROJECT_DIR/llm-wiki`, symlinks resolved):
    1. Secret scan (Write/Edit): if the introduced text carries a likely credential
       (per `secret_scan.py`), **deny**. This is the security floor and it fails *closed* — a
       scanner error on an in-bundle write denies rather than waving it through unscanned. A
       secret deny takes precedence and short-circuits the Doctor check.
    2. Doctor conformance (Write only): a full-content concept `.md` write that violates a
       per-file hard rule (R1 parseable frontmatter, R2 non-empty `type`) is denied. This is a
       conformance guard, not a security one, so it fails *open* on ambiguity — a guard must
       never wedge the session. Edit is not validated (it doesn't carry the whole
       resulting file, and the pre-existing file already passed) and the engine-owned reserved
       files (`index.md`, `log.md`) are out of per-call scope.

Scope (deliberate): general main-session `Bash` redirection and `NotebookEdit` are not covered. The
background Scribe is narrower: this hook limits its Write capability to secret-scanned `/tmp` staging,
and a separate Bash hook permits only the fixed publication/apply commands.

Fail policy: decisions are carried via stdout JSON (`permissionDecision: "deny"`); the script
always exits 0 (the decision lives in the JSON, not the exit code). It fails *open* only when it
cannot identify an in-bundle target (unparseable/non-object event, no/non-string path, non-bundle
path) — never wedging unrelated writes. Once a write is confirmed in-bundle, the secret floor fails
*closed*.
"""
import json
import os
import sys
import tempfile

import _hook_common
from secret_scan import scan
from doctor import check_concept


def _bundle_root(event):
    # realpath resolves symlinks so a write reaching the bundle via a symlinked path
    # can't slip past the under-bundle check (it leaves a non-existent tail intact).
    # S4 (accepted, no behavior change): if CLAUDE_PROJECT_DIR is unset and cwd is wrong,
    # project_dir resolves to the wrong root and the guard fails open — inherent to hook env
    # resolution; the containment check below is only as trustworthy as this resolution.
    return os.path.realpath(_hook_common.bundle_root(_hook_common.project_dir(event)))


def _introduced_text(tool_name, tool_input):
    """The text this tool would add — all we can meaningfully scan pre-write."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("new_string", "")
    return ""


def _deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def _scribe(event):
    value = event.get("agent_type")
    return isinstance(value, str) and value.rsplit(":", 1)[-1] == "wiki-capturer"


def _temp_staging_path(path):
    real = os.path.realpath(path)
    roots = {os.path.realpath("/tmp"), os.path.realpath(tempfile.gettempdir())}
    return (
        os.path.splitext(real)[1].lower() in (".json", ".md")
        and any(_hook_common.under(real, root) for root in roots)
    )


def main():
    event = _hook_common.read_event()
    if event is None:
        return 0  # can't identify a target → fail open (never wedge unrelated writes)
    fp = _hook_common.event_file_path(event)
    if fp is None:
        return 0
    tool_input = event.get("tool_input") or {}
    tool_name = event.get("tool_name", "")
    if _scribe(event):
        if tool_name != "Write" or not _temp_staging_path(fp):
            _deny("Wiki Scribe Write is restricted to .json/.md staging files under /tmp.")
            return 0
        try:
            findings = scan(_introduced_text(tool_name, tool_input))
        except Exception as exc:  # noqa: BLE001 - Scribe staging is a publication input
            _deny("Wiki Scribe staging could not be secret-scanned (%s)." % type(exc).__name__)
            return 0
        if findings:
            _deny("Wiki Scribe staging was blocked by the secret scan.")
        return 0
    if not _hook_common.under(os.path.realpath(fp), _bundle_root(event)):
        return 0  # not a bundle write — not our concern

    # (1) Secret floor. Confirmed in-bundle: from here the scan fails CLOSED — a scanner error
    # denies, not allows. A secret deny takes precedence and short-circuits the Doctor check.
    try:
        findings = scan(_introduced_text(tool_name, tool_input))
    except Exception as e:  # noqa: BLE001 — a security floor must not wave a write through on its own bug
        _deny("llm-wiki secret guard could not scan this in-bundle write (%s); failing closed — "
              "retry, or write outside the bundle." % type(e).__name__)
        return 0
    if findings:
        detail = "; ".join("%s (%s)" % (f["category"], f["preview"]) for f in findings)
        _deny("llm-wiki secret guard blocked this write — %d potential secret(s): %s. "
              "Remove or redact the credential before writing." % (len(findings), detail))
        return 0

    # (2) Doctor conformance — Write only; reserved files are engine-owned. An Edit
    # doesn't carry the whole resulting file, so it can't be checked per-call (deferred to the
    # command-orchestration Doctor). Fails open on ambiguity — conformance, not security.
    if tool_name != "Write":
        return 0
    if not fp.endswith(".md") or os.path.basename(fp) in ("index.md", "log.md"):
        return 0  # not a concept file (reserved files are engine-owned)
    content = tool_input.get("content", "")
    if content.startswith("﻿"):
        content = content[1:]  # strip a leading UTF-8 BOM so R1's leading-`---` check sees line 1 (matches doctor.validate)
    findings = []
    check_concept(content, os.path.basename(fp), findings)
    errors = [f for f in findings if f["severity"] == "ERROR"]
    if errors:
        _deny("llm-wiki Doctor guard blocked this write: " + "; ".join(
            "%s — %s" % (f["rule"], f["message"]) for f in errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
