#!/usr/bin/env python3
"""SessionStart hook — preload the llm-wiki into context (deterministic, no model call).

If a bundle exists at `$CLAUDE_PROJECT_DIR/llm-wiki/`, inject its root `index.md` plus a
one-line active-mode notice via the SessionStart `additionalContext` channel, so each
session starts knowing the wiki's shape and whether it is in auto (proactive) mode. If no
bundle exists, emit nothing and exit 0 — never block or noise a session that has no wiki.

Reads `$CLAUDE_PROJECT_DIR` (falls back to the event JSON's `cwd`, else cwd).
"""
import json
import os
import sys

from mode import resolve_mode

MODE_NOTE = {
    "proactive": "auto — findings are captured and indexes/log maintained without per-write "
                 "confirmation (every write is secret-scanned, Doctor-gated, logged, and git-reversible). "
                 "Switch with `mode: curated` in .claude/llm-wiki.local.md.",
    "curated": "propose-only — captures are proposed, never written without your confirmation.",
    "max": "auto + background curation (proactive plus the deferred Max tail).",
}


def _bundle_summary(bundle_dir):
    """(concept_count, sorted_tags) for the cold-start visibility line — so a near-empty bundle
    still shows what is queryable and the read step feels worthwhile early. Best-effort: any parse
    error just omits that concept's tags."""
    from doctor import classify, parse_frontmatter  # local import: only on the SessionStart path
    count, tags = 0, set()
    for root, _dirs, files in os.walk(bundle_dir):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            if classify(path, bundle_dir) != "concept":
                continue
            count += 1
            try:
                _status, fm = parse_frontmatter(open(path, encoding="utf-8").read())
            except OSError:
                continue
            if isinstance(fm, dict) and isinstance(fm.get("tags"), list):
                tags.update(str(t) for t in fm["tags"])
    return count, sorted(tags)


def _project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return env
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if isinstance(event, dict) and event.get("cwd"):
            return event["cwd"]
    except (ValueError, OSError):
        pass
    return os.getcwd()


def main():
    project_dir = _project_dir()
    index_path = os.path.join(project_dir, "llm-wiki", "index.md")
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            index = fh.read()
    except OSError:
        return 0  # no bundle here — contribute nothing

    mode = resolve_mode(project_dir)
    count, tags = _bundle_summary(os.path.join(project_dir, "llm-wiki"))
    summary = "**%d concept%s**%s" % (
        count, "" if count == 1 else "s",
        (" · tags: " + ", ".join(tags)) if tags else "",
    )
    context = (
        "# llm-wiki knowledge bundle (preloaded)\n\n"
        "Active mode: **%s** — %s\n\n"
        "%s — consult via `/llm-wiki:query` / `:explore` before non-trivial work; capture durable "
        "findings as you go.\n\n"
        "Root index (`llm-wiki/index.md`):\n\n"
        "%s" % (mode, MODE_NOTE.get(mode, ""), summary, index)
    )
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
