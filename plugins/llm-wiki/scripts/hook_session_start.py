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
import re
import sys
import time

import _hook_common

# a stale session-scoped marker is pure litter (hook_stop only consumes its own session's);
# a day is comfortably past any live session while still bounding the accumulation
_MARKER_MAX_AGE_S = 86400

# A root-index concept bullet: `* [Title](./path.md) — description`. The captured group keeps the
# bullet through the link's closing `)`, so the titles-only cap can drop the ` — description` tail.
_CONCEPT_BULLET = re.compile(r"^(\s*[*-] \[[^\]]*\]\([^)]*\))")

# Shared start-of-session "consult the wiki" guidance, used here in the SessionStart preload and
# re-used by the UserPromptSubmit nudge (hook_user_prompt.py imports it) so the two cannot drift.
# Phrased to begin lower-case so it reads as a clause joined onto each hook's own lead-in.
CONSULT_GUIDANCE = (
    "consult it before any non-trivial work via `/llm-wiki:query` — proactively and WITHOUT asking the "
    "user first (reading the wiki first is the default expectation, not opt-in); trust it as a curated "
    "summary, then verify a load-bearing claim against current state before acting (the concept says "
    "where to look, so it's quick); capture durable findings as you go."
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


def _titles_only(index):
    """Return (body, n_bullets): each concept bullet trimmed to `* [Title](./path.md)` (drop the
    ` — description` tail); non-bullet lines (headings, prose, blanks) pass through untouched."""
    out, n = [], 0
    for line in index.split("\n"):
        m = _CONCEPT_BULLET.match(line)
        if m:
            n += 1
            out.append(m.group(1))
        else:
            out.append(line)
    return "\n".join(out), n


def _sweep_stale_markers(project):
    """Hygiene for `capture-pending*` markers left by dead sessions: a session-scoped marker is
    never consumed by any other session (hook_stop reads only its own), and a legacy unsuffixed
    one can linger from a killed pre-session-scoping session — either would otherwise sit forever
    (legacy: until it fires a phantom nudge on an old CLI that pairs on the unsuffixed name).
    Legacy goes immediately; session-scoped only past _MARKER_MAX_AGE_S, so a *concurrent* live
    session's armed marker survives another session starting up. Best-effort: bookkeeping never
    breaks a SessionStart."""
    marker_dir = os.path.dirname(_hook_common.capture_marker(project))
    try:
        names = os.listdir(marker_dir)
    except OSError:
        return
    now = time.time()
    for name in names:
        if not name.startswith("capture-pending"):
            continue
        path = os.path.join(marker_dir, name)
        try:
            if name == "capture-pending" or now - os.path.getmtime(path) > _MARKER_MAX_AGE_S:
                os.remove(path)
        except OSError:
            pass


def _event():
    try:
        event = json.loads(sys.stdin.read() or "{}")
        return event if isinstance(event, dict) else {}
    except (ValueError, OSError):
        return {}


def main():
    event = _event()
    project_dir = _hook_common.project_dir(event)
    index_path = os.path.join(_hook_common.bundle_root(project_dir), "index.md")
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            index = fh.read()
    except OSError:
        # No bundle here. On a fresh `startup` only, leave one terse pointer so a new repo discovers
        # the plugin; stay silent on resume/clear/compact, and create no marker/state file.
        if event.get("source") == "startup":
            json.dump({"hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "[llm-wiki] No knowledge bundle in this repo yet — /llm-wiki:ingest --dry-run "
                    "previews bootstrapping one from the codebase; /llm-wiki:capture saves findings "
                    "as you go."
                ),
            }}, sys.stdout)
        return 0  # no bundle — otherwise contribute nothing

    if event.get("source") != "compact":
        # not on compact: that's mid-session, and on a no-session_id CLI the sweep would eat the
        # session's own in-flight legacy marker
        _sweep_stale_markers(project_dir)

    count, tags = _bundle_summary(_hook_common.bundle_root(project_dir))
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
        body, n_bullets = _titles_only(index)
        # A large root index defeats the point of a lean preload — cap it to titles-only past either
        # bound, and nudge toward the maintenance commands that keep the preload small.
        if n_bullets > 40 or len(index.encode("utf-8")) > 16384:
            head += (
                "index shown titles-only (%d concepts) — full descriptions in %s\n"
                "bundle is large — /llm-wiki:reorganize into sections keeps this preload lean; "
                "/llm-wiki:tend for a health digest.\n\n" % (n_bullets, index_path)
            )
            context = head + "Root index (`llm-wiki/index.md`):\n\n" + body
        else:
            context = head + "Root index (`llm-wiki/index.md`):\n\n" + index
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
