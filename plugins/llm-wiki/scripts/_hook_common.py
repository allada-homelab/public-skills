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
import hashlib

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


def session_state_path(project, stem, session_id=None):
    """A filename-safe, session-scoped transient state path inside the bundle."""
    token = _SESSION_ID_UNSAFE.sub("_", str(session_id or "__nosession__"))
    return os.path.join(bundle_root(project), ".llm-wiki", "%s-%s" % (stem, token))


def session_state_dir(project, session_id=None):
    """Collision-resistant session state directory; raw session IDs never become paths."""
    raw = str(session_id or "__nosession__")
    prefix = _SESSION_ID_UNSAFE.sub("_", raw)[:24] or "session"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return os.path.join(bundle_root(project), ".llm-wiki", "sessions", "%s-%s" % (prefix, digest))


def under(path_abs, root_abs):
    """True when `path_abs` is at or below `root_abs` (both should already be absolute/realpath'd)."""
    try:
        return os.path.commonpath([root_abs, path_abs]) == root_abs
    except ValueError:
        return False  # different drives / unrelated roots


def read_event():
    """Parse the hook event from stdin. None unless it is a JSON object —
    a crash here would exit nonzero, which Claude Code treats as
    NON-blocking, silently failing the guards open."""
    import json, sys
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeDecodeError):
        return None
    return event if isinstance(event, dict) else None


def emit_additional_context(event_name, context, limit=8000):
    """Emit bounded hook JSON, preserving a closing llm-wiki data marker if truncation is needed."""
    import json, sys

    def render(value):
        return json.dumps({"hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": value,
        }}, ensure_ascii=False, separators=(",", ":"))

    payload = render(context)
    if len(payload) <= limit:
        sys.stdout.write(payload)
        return

    marker = "<<<END_LLM_WIKI_UNTRUSTED_DATA>>>"
    suffix = "\n[truncated to llm-wiki hook limit]"
    if "<<<LLM_WIKI_UNTRUSTED_DATA:" in context:
        suffix += "\n" + marker
    low, high, best = 0, len(context), render(suffix)
    while low <= high:
        mid = (low + high) // 2
        candidate = context[:mid].rstrip() + suffix
        rendered = render(candidate)
        if len(rendered) <= limit:
            best = rendered
            low = mid + 1
        else:
            high = mid - 1
    sys.stdout.write(best)


def event_file_path(event):
    """tool_input.file_path, only if actually a non-empty string."""
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    fp = tool_input.get("file_path")
    return fp if isinstance(fp, str) and fp else None


def load_settings(project_dir):
    """Read .claude/llm-wiki.local.md YAML frontmatter (flat `key: value`
    lines only — stdlib, no YAML dep). Defaults on any error."""
    settings = {
        "capture_nudge": "on",
        "capture_min_edits": 1,
        "sensitive_paths": (),
        "autonomy": "on",
        "autonomy_disabled": (),
        "autonomy_max_calls": 12,
        "autonomy_max_turns": 120,
        "autonomy_max_seconds": 480,
        "autonomy_max_descendants": 4,
        "autonomy_max_depth": 2,
        "autonomy_cooldowns": {
            "recall": 0,
            "capture": 30,
            "impact": 30,
            "scribe": 30,
            "gap": 300,
            "parallel": 0,
        },
    }
    path = os.path.join(project_dir, ".claude", "llm-wiki.local.md")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return settings
    if not lines or lines[0].strip() != "---":
        return settings
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip().strip("'\"")
        if key == "capture_nudge" and value in ("on", "off"):
            settings["capture_nudge"] = value
        elif key == "capture_min_edits":
            try:
                settings["capture_min_edits"] = max(1, int(value))
            except ValueError:
                pass
        elif key == "sensitive_paths":
            settings["sensitive_paths"] = tuple(
                part.strip() for part in value.split(",") if part.strip()
            )
        elif key == "autonomy" and value in ("on", "off"):
            settings["autonomy"] = value
        elif key == "autonomy_disabled":
            settings["autonomy_disabled"] = tuple(
                part.strip().lower() for part in value.split(",") if part.strip()
            )
        elif key in (
            "autonomy_max_calls",
            "autonomy_max_turns",
            "autonomy_max_seconds",
            "autonomy_max_descendants",
            "autonomy_max_depth",
        ):
            try:
                settings[key] = max(0, int(value))
            except ValueError:
                pass
        elif key == "autonomy_cooldowns":
            parsed = dict(settings["autonomy_cooldowns"])
            for item in value.split(","):
                feature, sep, seconds = item.partition("=")
                if not sep or not feature.strip():
                    continue
                try:
                    parsed[feature.strip().lower()] = max(0, int(seconds.strip()))
                except ValueError:
                    pass
            settings["autonomy_cooldowns"] = parsed
    return settings


def ensure_bundle_gitignore(bundle_root):
    """Keep transient .llm-wiki/ state out of the tracked wiki bundle."""
    path = os.path.join(bundle_root, ".gitignore")
    try:
        existing = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                existing = fh.read()
        if ".llm-wiki/" not in existing.split("\n"):
            with open(path, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(".llm-wiki/\n")
    except OSError:
        pass
