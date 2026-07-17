#!/usr/bin/env python3
"""SessionStart hook: inject a bounded recursive wiki metadata map without opening concept bodies."""

import os
import sys
import time

import _hook_common
from catalog import load_catalog, render_catalog
from evidence_ledger import EvidenceLedger
from trust_boundary import delimit


_MARKER_MAX_AGE_S = 86400

CONSULT_GUIDANCE = (
    "consult it before any non-trivial work via `/llm-wiki:query` — proactively and WITHOUT asking "
    "the user first; treat candidates as entry points, then verify load-bearing claims against current "
    "state before acting; capture durable findings as you go."
)


def _sweep_stale_markers(project):
    """Remove dead capture markers without consuming another live session's marker."""
    bundle = _hook_common.bundle_root(project)
    marker_dir = os.path.dirname(_hook_common.capture_marker(project))
    _hook_common.ensure_bundle_gitignore(bundle)
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


def _summary(catalog):
    count = len(catalog["entries"])
    section_count = sum(1 for section in catalog["sections"] if section["path"])
    return "**%d concept%s across %d section%s**" % (
        count,
        "" if count == 1 else "s",
        section_count,
        "" if section_count == 1 else "s",
    )


def main():
    event = _hook_common.read_event() or {}
    project = _hook_common.project_dir(event)
    bundle = _hook_common.bundle_root(project)
    if not _hook_common.bundle_exists(project):
        if event.get("source") == "startup":
            _hook_common.emit_additional_context(
                "SessionStart",
                "[llm-wiki] No knowledge bundle in this repo yet — /llm-wiki:ingest --dry-run "
                "previews bootstrapping one; /llm-wiki:capture saves findings as you go.",
            )
        return 0
    if not _hook_common.under(os.path.realpath(bundle), os.path.realpath(project)):
        return 0

    baseline = EvidenceLedger(project, event.get("session_id")).initialize()

    if event.get("source") != "compact":
        _sweep_stale_markers(project)

    catalog = load_catalog(bundle)
    head = "# llm-wiki knowledge bundle (preloaded)\n\n%s — %s\n\nllm-wiki session: `%s` (`%s`).\n\n" % (
        _summary(catalog), CONSULT_GUIDANCE, baseline["session_id"], baseline["run_id"]
    )
    if event.get("source") == "compact":
        context = head + "Use the proactive candidate envelope or re-read the recursive indexes as needed."
    else:
        descriptions = len(catalog["entries"]) <= 40
        mode = "titles + descriptions" if descriptions else "titles only"
        body = render_catalog(catalog, descriptions=descriptions)
        context = head + "Recursive catalog (%s):\n\n%s" % (mode, delimit("wiki_catalog", body))
    _hook_common.emit_additional_context("SessionStart", context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
