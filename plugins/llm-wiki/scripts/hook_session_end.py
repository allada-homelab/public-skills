"""SessionEnd digest — a brief, deterministic end-of-session summary of wiki activity.

Counts the change entries under the newest date heading in the bundle's `log.md` and prints
a one-line digest pointing at `/llm-wiki:tend` for a fuller review. SessionEnd is observe-only —
it cannot inject context, and its stdout at exit 0 goes to the debug log, not the transcript; so
the digest is surfaced to the user via the universal `systemMessage` JSON field (the documented
user-facing channel), not a bare print. Silent when there is no bundle or no logged changes.

Mode-gated: only emitted in **curated** mode. In an auto mode (`proactive`/`max`, the default)
captures land silently by design, so an end-of-session "here's what I saved" digest is exactly the
noise the user does not want — stay silent. Curated keeps it: there the user is hands-on, and the
`/llm-wiki:tend` pointer is a useful nudge.

Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import re
import sys

from bundle_path import bundle_root
from mode import resolve_mode

DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def _newest_day_changes(log_text):
    """(date, count) for the newest date heading, or (None, 0)."""
    lines = log_text.split("\n")
    date, count = None, 0
    for line in lines:
        m = DATE_HEADING.match(line)
        if m:
            if date is not None:
                break  # only the newest (first) day
            date = m.group(1)
        elif date is not None and line.lstrip().startswith("* **"):
            count += 1
    return date, count


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    if resolve_mode(project) != "curated":
        return 0  # auto modes capture silently — no end-of-session "what I saved" digest
    try:
        with open(os.path.join(bundle_root(project), "log.md"), "r", encoding="utf-8") as fh:
            log_text = fh.read()
    except OSError:
        return 0  # no bundle / no log — nothing to summarize
    date, count = _newest_day_changes(log_text)
    if not date or count == 0:
        return 0
    message = ("llm-wiki: %d change(s) logged on %s this session — run `/llm-wiki:tend` to review "
               "(staleness, broken links, gaps)." % (count, date))
    json.dump({"systemMessage": message}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
