#!/usr/bin/env python3
"""Resolve the llm-wiki autonomy mode for a project.

Reads `<project-dir>/.claude/llm-wiki.local.md` (git-ignored, per-project). The file is
optional; when absent / unreadable / unrecognized the mode defaults to **proactive**
(auto) — the Phase 3 default, made safe by the in-session secret + Doctor guards.

Usage: mode.py [project-dir]   (default: $CLAUDE_PROJECT_DIR, else cwd)
Prints exactly one of: proactive | curated | max
"""
import os
import re
import sys

MODES = ("proactive", "curated", "max")
DEFAULT = "proactive"
_MODE_RE = re.compile(r"(?mi)^[ \t]*mode[ \t]*:[ \t]*([A-Za-z]+)[ \t]*$")


def resolve_mode(project_dir):
    path = os.path.join(project_dir, ".claude", "llm-wiki.local.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return DEFAULT  # absent file → default (fresh checkout is auto)
    m = _MODE_RE.search(text)
    if m and m.group(1).lower() in MODES:
        return m.group(1).lower()
    return DEFAULT  # unrecognized/garbage → fail safe to the default


def main(argv):
    project_dir = argv[0] if argv else (os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    print(resolve_mode(project_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
