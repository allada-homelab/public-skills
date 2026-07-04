"""Shared path/scope helpers for the llm-wiki hook scripts.

Imported by the sibling `hook_*.py` / `*_guard.py` scripts (each script's own directory is
`sys.path[0]`, so a plain `import _hook_common` resolves — the same mechanism the existing
`from secret_scan import scan` / `from doctor import check_concept` sibling imports ride). Keep this
module **stdlib-only** and **side-effect-free at import** — it loads on every hook invocation and
must never emit output, read stdin, or touch disk at import time. The leading underscore marks it a
helper, not itself a hook.

These factor the security-relevant path/scope logic (project-dir resolution, bundle root/existence,
realpath containment, the capture-pending marker) into one definition so the hooks cannot drift.
Callers pass an already-parsed `event` dict / resolved `project` path — event JSON parsing stays in
each hook because its error policy genuinely differs between them.
"""
import os
import re

BUNDLE_DIRNAME = "llm-wiki"

# session_id lands in a filename — keep only filename-safe chars so a malformed id can't traverse
_SESSION_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def project_dir(event):
    """Resolve the project root: `$CLAUDE_PROJECT_DIR`, else the event's `cwd`, else `os.getcwd()`."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()


def bundle_root(project):
    """The default bundle directory `<project>/llm-wiki` (not realpath-resolved; callers realpath
    when they need symlink-safe containment)."""
    return os.path.join(project, BUNDLE_DIRNAME)


def bundle_exists(project):
    """True when a bundle is present, detected by its root `index.md` via `isfile` on the raw
    (non-realpath) path — matching the hooks' existing existence check."""
    return os.path.isfile(os.path.join(bundle_root(project), "index.md"))


def capture_marker(project, session_id=None):
    """The `capture-pending` marker path — PostToolUse drops it, Stop consumes it. One definition
    so the producer and consumer cannot drift.

    Session-scoped (`capture-pending-<session_id>`): the marker is on-disk per *project*, but its
    meaning is per *session* ("this session's turn changed real code") — an unscoped name lets any
    concurrent Claude process in the project (a headless background job, a parallel session) arm
    another session's Stop nudge, and lets a killed session's stale marker fire on the next
    session's first stop. Falls back to the legacy unsuffixed name when the event carries no
    `session_id` (older CLIs) — producer and consumer then still pair on the same path."""
    name = "capture-pending"
    if session_id:
        name += "-" + _SESSION_ID_UNSAFE.sub("_", str(session_id))
    return os.path.join(bundle_root(project), ".llm-wiki", name)


def under(path_abs, root_abs):
    """True when `path_abs` is at or below `root_abs` (both should already be absolute/realpath'd)."""
    try:
        return os.path.commonpath([root_abs, path_abs]) == root_abs
    except ValueError:
        return False  # different drives / unrelated roots
