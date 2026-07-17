#!/usr/bin/env python3
"""PreToolUse path policy for llm-wiki read-only reasoning agents.

The policy is capability enforcement, not a prompt request: protected agents may read ordinary
repository evidence, but not paths outside the project, common credential stores, secret-like files,
or project-specific paths configured in `.claude/llm-wiki.local.md`.
"""

import fnmatch
import json
import os
import sys

import _hook_common


_PROTECTED_AGENTS = frozenset({
    "wiki-verifier",
    "wiki-explorer",
    "wiki-coprocessor",
    "wiki-compiler",
    "wiki-glimmer",
    "wiki-archaeologist",
    "wiki-sentinel",
    "wiki-impact", "wiki-researcher",
})
_SENSITIVE_DIRS = frozenset({".git", ".ssh", ".aws", ".gnupg", ".kube", ".claude", ".codex"})
_SENSITIVE_FILES = frozenset({
    ".env",
    "credentials",
    "credentials.json",
    "application_default_credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
})
_SENSITIVE_SUFFIXES = (".key", ".p12", ".pfx", ".pem")
_SEARCH_SCAN_LIMIT = 10000


def _agent_name(event):
    value = event.get("agent_type")
    if not isinstance(value, str):
        return ""
    return value.rsplit(":", 1)[-1]


def _deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def _resolve(project, value):
    if not isinstance(value, str) or not value:
        return None
    path = value if os.path.isabs(value) else os.path.join(project, value)
    return os.path.realpath(path)


def _common_sensitive(path):
    parts = [part.lower() for part in os.path.normpath(path).split(os.sep) if part]
    if any(part in _SENSITIVE_DIRS for part in parts):
        return True
    if any(parts[index:index + 2] == [".config", "gcloud"] for index in range(len(parts) - 1)):
        return True
    name = parts[-1] if parts else ""
    return (
        name in _SENSITIVE_FILES
        or name.startswith(".env.")
        or name.endswith(_SENSITIVE_SUFFIXES)
    )


def _configured_sensitive(path, project, configured):
    for value in configured:
        root = _resolve(project, value)
        if root is not None and _hook_common.under(path, root):
            return True
    return False


def _unsafe_glob(pattern):
    if not isinstance(pattern, str) or not pattern:
        return False
    normalized = pattern.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if normalized.startswith("/") or ".." in parts:
        return True
    if any(part in _SENSITIVE_DIRS for part in parts):
        return True
    if ".config/gcloud" in normalized:
        return True
    return any(
        fnmatch.fnmatch(part, ".env*")
        or part in _SENSITIVE_FILES
        or part.endswith(_SENSITIVE_SUFFIXES)
        for part in parts
    )


def _literal_glob_root(project, base, pattern):
    """Narrow a search to the literal prefix before its first glob metacharacter."""
    if not isinstance(pattern, str) or not pattern:
        return base
    parts = pattern.replace("\\", "/").split("/")
    literal = []
    for part in parts:
        if any(char in part for char in "*?["):
            break
        if part not in ("", "."):
            literal.append(part)
    return _resolve(project, os.path.join(base, *literal)) if literal else base


def _tree_contains_sensitive(root, project, configured):
    """Fail closed when a broad search root contains a denied descendant."""
    for value in configured:
        configured_root = _resolve(project, value)
        if configured_root is not None and _hook_common.under(configured_root, root):
            return True
    visited = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        visited += len(dirs) + len(files) + 1
        if visited > _SEARCH_SCAN_LIMIT:
            return True
        if _common_sensitive(current):
            return True
        for name in dirs + files:
            if _common_sensitive(os.path.join(current, name)):
                return True
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(current, name))]
    return False


def main():
    event = _hook_common.read_event()
    if event is None or _agent_name(event) not in _PROTECTED_AGENTS:
        return 0

    tool_name = event.get("tool_name")
    tool_input = event.get("tool_input")
    if tool_name not in ("Read", "Grep", "Glob") or not isinstance(tool_input, dict):
        return 0

    project = os.path.realpath(_hook_common.project_dir(event))
    if tool_name == "Read":
        target = _resolve(project, tool_input.get("file_path"))
        if target is None:
            _deny("llm-wiki read policy could not scope this file read; provide a repository path.")
            return 0
    else:
        target = _resolve(project, tool_input.get("path") or project)
        path_pattern = tool_input.get("pattern") if tool_name == "Glob" else tool_input.get("glob")
        if _unsafe_glob(path_pattern):
            _deny("llm-wiki read policy blocked a glob that could reach sensitive or out-of-project paths.")
            return 0
        target = _literal_glob_root(project, target, path_pattern)

    settings = _hook_common.load_settings(project)
    agent = _agent_name(event)
    scoped_feature = {"wiki-researcher": "gap", "wiki-explorer": "ingest_worker"}.get(agent)
    if scoped_feature and tool_name == "Read":
        from job_state import JobController
        allowed = JobController(project, event.get("session_id")).authorized_reads(scoped_feature)
        if target not in allowed:
            _deny("llm-wiki read policy blocked a path outside this controller-issued source manifest.")
            return 0
    if not _hook_common.under(target, project):
        _deny("llm-wiki read policy keeps autonomous evidence reads inside the project.")
    elif _common_sensitive(target) or _configured_sensitive(
        target, project, settings["sensitive_paths"]
    ):
        _deny("llm-wiki read policy blocked a sensitive path; use an explicitly authorized main-session read instead.")
    elif tool_name in ("Grep", "Glob") and _tree_contains_sensitive(
        target, project, settings["sensitive_paths"]
    ):
        _deny("llm-wiki read policy blocked a broad search whose scope contains sensitive paths; narrow it to an explicit safe subtree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
