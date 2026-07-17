#!/usr/bin/env python3
"""PreToolUse capability gate: Scribe may run only the fixed publication/apply pipeline."""

import json
import os
import shlex
import sys
import tempfile

import _hook_common


def _agent(event):
    value = event.get("agent_type")
    return value.rsplit(":", 1)[-1] if isinstance(value, str) else ""


def _deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def _script(token, name):
    plugin = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
    expected = os.path.join(plugin, "scripts", name)
    expanded = token.replace("${CLAUDE_PLUGIN_ROOT}", plugin)
    return os.path.realpath(expanded) == os.path.realpath(expected)


def _temp_path(value):
    if not isinstance(value, str) or not os.path.isabs(value):
        return False
    real = os.path.realpath(value)
    roots = {os.path.realpath("/tmp"), os.path.realpath(tempfile.gettempdir())}
    return any(_hook_common.under(real, root) for root in roots)


def _option(tokens, name):
    try:
        index = tokens.index(name)
    except ValueError:
        return None
    return tokens[index + 1] if index + 1 < len(tokens) else None


def _allowed_publication(tokens):
    return (
        len(tokens) == 4
        and tokens[0] == "python3"
        and _script(tokens[1], "publication.py")
        and _temp_path(tokens[2])
        and _temp_path(tokens[3])
    )


def _allowed_apply(tokens, project):
    if len(tokens) < 10 or tokens[0] != "python3" or not _script(tokens[1], "bundle_ops.py"):
        return False
    if tokens[2] != "apply" or os.path.realpath(tokens[3]) != os.path.realpath(_hook_common.bundle_root(project)):
        return False
    concept = _option(tokens, "--concept")
    content_file = _option(tokens, "--content-file")
    kind = _option(tokens, "--log-kind")
    message = _option(tokens, "--log-message")
    if not all((concept, content_file, kind, message)) or kind not in ("Creation", "Update"):
        return False
    if os.path.isabs(concept) or ".." in concept.replace("\\", "/").split("/") or not concept.endswith(".md"):
        return False
    if not _temp_path(content_file):
        return False
    allowed_flags = {"--concept", "--content-file", "--log-kind", "--log-message", "--date"}
    return all(not token.startswith("--") or token in allowed_flags for token in tokens[4:])


def main():
    event = _hook_common.read_event()
    if event is None or event.get("tool_name") != "Bash" or _agent(event) != "wiki-capturer":
        return 0
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or any(value in command for value in (";", "|", "&", ">", "<", "\n", "\r", "`", "$(")):
        _deny("Wiki Scribe permits one fixed publication command with no shell composition.")
        return 0
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = []
    if not (_allowed_publication(tokens) or _allowed_apply(tokens, _hook_common.project_dir(event))):
        _deny("Wiki Scribe Bash is restricted to publication.py and gated bundle_ops.py apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
