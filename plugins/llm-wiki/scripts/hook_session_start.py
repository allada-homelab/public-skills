#!/usr/bin/env python3
"""SessionStart hook: inject a bounded recursive wiki metadata map without opening concept bodies."""

import os
import subprocess
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


def _prior_bundle_evidence(project, bundle):
    """A signal that a bundle existed at this root before, distinguishing 'vanished' from 'never
    had one': a non-empty bundle directory (e.g. leftover `.llm-wiki/` state after index.md was
    lost), else bundle files tracked in git — the load-bearing signal after a whole-directory
    rename-away, since `.llm-wiki/` state moves *with* the directory. Both checks are best-effort;
    None means no evidence (the quiet no-bundle state stays quiet)."""
    try:
        if os.path.isdir(bundle) and os.listdir(bundle):
            return "the directory is non-empty"
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["git", "-C", project, "ls-files", "--", os.path.relpath(bundle, project)],
            capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            return "git tracks %d file(s) under it" % len(proc.stdout.strip().splitlines())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


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
        # "Never had a wiki" is a quiet state by design — but "had one and it vanished" must be
        # loud: without this, renaming/emptying the bundle silently disables the whole coprocessor
        # while every health signal reads green. Emitted on every source, compaction included.
        evidence = _prior_bundle_evidence(project, bundle)
        if evidence:
            _hook_common.emit_additional_context(
                "SessionStart",
                "[llm-wiki] WIKI MISSING — `%s` has no root index.md, but %s. A bundle existed "
                "here before: it has likely been moved, renamed, or emptied, and the wiki "
                "coprocessor is disabled until it is restored. Surface this to the user "
                "prominently, and restore the bundle (move it back, or `git checkout -- %s`) "
                "rather than re-ingesting from scratch." % (bundle, evidence, bundle),
            )
        elif event.get("source") == "startup":
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
