#!/usr/bin/env python3
"""SessionStart hook — preload the llm-wiki into context (deterministic, no model call).

If a bundle exists at `$CLAUDE_PROJECT_DIR/llm-wiki/`, inject a concept/tag summary via the
SessionStart `additionalContext` channel, so each session starts knowing the wiki's shape. If no
bundle exists, emit nothing and exit 0 — never block or noise a session that has no wiki.

Branches on the event `source` (startup/resume/clear/compact): on a fresh/resumed/cleared
session the full root `index.md` body is injected; on `source == "compact"` only the shorter
pointer (summary, *not* the index body) is injected — re-injecting the whole index
on every compaction would partially defeat compaction and grow with the bundle.

Reads `$CLAUDE_PROJECT_DIR` (falls back to the event JSON's `cwd`, else cwd).
"""
import json
import os
import sys

# Shared start-of-session "consult the wiki" guidance, used here in the SessionStart preload and
# re-used by the UserPromptSubmit nudge (hook_user_prompt.py imports it) so the two cannot drift.
# Phrased to begin lower-case so it reads as a clause joined onto each hook's own lead-in.
CONSULT_GUIDANCE = (
    "consult it before non-trivial work via `/llm-wiki:query` or `/llm-wiki:explore`; trust it as a "
    "curated summary, then verify a load-bearing claim against current state before acting (the "
    "concept says where to look, so it's quick); capture durable findings as you go."
)


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
                with open(path, encoding="utf-8") as fh:
                    _status, fm = parse_frontmatter(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            if isinstance(fm, dict) and isinstance(fm.get("tags"), list):
                tags.update(str(t) for t in fm["tags"])
    return count, sorted(tags)


def _event():
    try:
        event = json.loads(sys.stdin.read() or "{}")
        return event if isinstance(event, dict) else {}
    except (ValueError, OSError):
        return {}


def main():
    event = _event()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    index_path = os.path.join(project_dir, "llm-wiki", "index.md")
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            index = fh.read()
    except OSError:
        return 0  # no bundle here — contribute nothing

    count, tags = _bundle_summary(os.path.join(project_dir, "llm-wiki"))
    summary = "**%d concept%s**%s" % (
        count, "" if count == 1 else "s",
        (" · tags: " + ", ".join(tags)) if tags else "",
    )
    head = (
        "# llm-wiki knowledge bundle (preloaded)\n\n"
        "%s — %s\n\n" % (summary, CONSULT_GUIDANCE)
    )
    if event.get("source") == "compact":
        # post-compaction: the full index is (or just was) in context — inject only the pointer,
        # not the whole index body, so we don't grow with the bundle or partially undo compaction.
        context = head + "Re-read `llm-wiki/index.md` if you need the full concept map."
    else:
        context = head + "Root index (`llm-wiki/index.md`):\n\n" + index
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
