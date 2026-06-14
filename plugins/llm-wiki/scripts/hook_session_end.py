"""SessionEnd digest — a brief, deterministic end-of-session summary of wiki activity.

Counts the change entries under the newest date heading in the bundle's `log.md` and prints
a one-line digest pointing at `/llm-wiki:tend` for a fuller review. Plain text (SessionEnd
is observe-only — it cannot inject context, so this surfaces via the session transcript/log,
not the model's context). Silent when there is no bundle or no logged changes.

Reads `$CLAUDE_PROJECT_DIR` (falls back to event `cwd`).
"""
import json
import os
import re
import sys

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
    try:
        with open(os.path.join(project, "llm-wiki", "log.md"), "r", encoding="utf-8") as fh:
            log_text = fh.read()
    except OSError:
        return 0  # no bundle / no log — nothing to summarize
    date, count = _newest_day_changes(log_text)
    if not date or count == 0:
        return 0
    print("llm-wiki: %d change(s) logged on %s this session — run `/llm-wiki:tend` to review "
          "(staleness, broken links, gaps)." % (count, date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
