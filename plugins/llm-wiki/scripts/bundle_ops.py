#!/usr/bin/env python3
"""Deterministic OKF bundle maintenance ("durability engine") for the /llm-wiki plugin.

Stdlib-only. Three in-place operations the Phase 2 maintenance commands compose; the
commands stage a /tmp bundle mirror, run these against it, then Doctor-gate + confirm
before copying back. Conformance is *not* this script's job — the Doctor is the
authority (run it after).

    bundle_ops.py index <bundle-root>
        Regenerate every index.md from concept frontmatter. The preamble (everything
        above the first `## ` heading) is preserved verbatim; the `## Concepts` /
        `## Sections` listings below it are machine-owned. Root index keeps only
        `okf_version` frontmatter; subdir index.md gets zero frontmatter.

    bundle_ops.py log-append <bundle-root> --kind Creation|Update|Initialization
                  --message <markdown> [--date YYYY-MM-DD]
        Insert `* **<Kind>**: <message>` newest-first under the date heading
        (creating today's heading at the top if needed). `<message>` must be a
        single line — a newline-bearing message is rejected (exit 2).

    bundle_ops.py move <bundle-root> --from <relpath> --to <relpath>
        Move a concept and rewrite every inbound link across the bundle in BOTH the
        relative (`./`) and bundle-relative (`/`) forms, plus the relative links
        *inside* the moved file (whose anchor directory changed). Indexes are NOT
        regenerated here — run `index` afterward.

    bundle_ops.py remove <bundle-root> --concept <relpath>
        Delete one concept file (guarded: refuses reserved files and paths outside the
        bundle). Inbound links are intentionally left for the Doctor to report (R4) —
        per spec §6.1 broken links are tolerated, never silently rewritten away.

    bundle_ops.py apply <bundle-root> --concept <relpath> --content-file <path>
                  [--log-kind Creation|Update|Initialization] [--log-message <md>]
                  [--date YYYY-MM-DD] [--generated-by <actor>]
        The consolidated gated write. Auto-initializes an absent bundle, stamps the OKF
        v0.2 `generated: { by, at }` field when the content lacks one (`--generated-by`
        names the §7 actor, e.g. `llm-wiki/claude-opus-5`), migrates any legacy v0.1
        concepts in the bundle to v0.2 field shape, stages the
        concept on a /tmp mirror (index regen + log append), Doctor-gates (strict) and
        secret-scans it, and only on a clean gate copies the result onto the LIVE bundle
        (a block leaves its concepts/index/log byte-for-byte untouched; only the
        transient `.llm-wiki/` state dir and its `.gitignore` guard may appear).
        Emits a one-line JSON status (applied | blocked:doctor | blocked:secret).
        Exit 1 on a gate block.

    bundle_ops.py batch-apply <bundle-root> --manifest <prepared-manifest.json>
                  [--date YYYY-MM-DD]
        Apply a bounded set of already provenance-stamped concepts under one bundle lock, one
        mirror/Doctor/secret gate, one index regeneration, and one log entry.

    bundle_ops.py stage <bundle-root>
        Stage the bundle's current git state (`git add -A` scoped to the bundle directory)
        while holding the same bundle lock `apply` holds, so staging can never snapshot a
        half-landed background apply (concept written, index/log not yet). Use this — or
        re-stage bundle paths immediately before committing — whenever a commit includes
        the bundle; a live session's Scribe may apply concurrently at any time.

    bundle_ops.py linkcheck <bundle-root>
        Report every internal markdown link as one JSON object on stdout:
        {"status": "ok", "links": [{file, line, raw, resolved, exists}]}. External
        schemes and bare #anchors are skipped. Report-only: exit 0 even when links
        are broken.

    bundle_ops.py merge <bundle-root>
        Resolve git conflict markers in log.md (union of both sides' bullets under
        their `## YYYY-MM-DD` headings, deduped, newest-first) and index.md
        (conflicted content discarded), then regenerate indexes and Doctor-gate the
        result. JSON status merged | clean | blocked:doctor; a doctor block (exit 1)
        leaves the merged files in place for inspection.

Exit codes: 0 ok; 1 gate block (apply, merge); 2 usage / operational error.
"""
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import subprocess
from contextlib import contextmanager
from datetime import date, datetime, timezone

# doctor.py / secret_scan.py live beside this script; when run directly Python puts
# that dir on sys.path[0], but insert it explicitly so `apply` also resolves them when
# bundle_ops is imported as a module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doctor as _doctor          # noqa: E402
import secret_scan as _secret_scan  # noqa: E402

# The generator-owned root index frontmatter. Sourced from the Doctor's constant so the
# emitted version and the version R3b enforces can never drift apart.
_ROOT_FRONTMATTER = '---\nokf_version: "%s"\n---\n' % _doctor.OKF_VERSION

# C2 decision of record: near-duplicate of doctor.py's LINK_RE kept deliberately — the
# rewriter needs the pre/post capture groups doctor's URL-only pattern doesn't have.
LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)]+)(\))")
# A line opening/closing a fenced code block (``` or ~~~), toggled per-line so the
# link rewriter never mutates link-shaped text inside a fenced example. Shared with
# doctor.py verbatim (identical grammar), so imported rather than re-defined (C2).
FENCE_RE = _doctor.FENCE_RE
# A run of backticks delimiting an inline-code span; an opener is closed by the next
# run of EQUAL length (CommonMark), so link-shaped text inside `…` is left verbatim.
BACKTICK_RUN_RE = re.compile(r"`+")
EXTERNAL_SCHEMES = _doctor.EXTERNAL_SCHEMES  # identical tuple — shared with doctor.py (C2)
RESERVED = ("index.md", "log.md")
MANAGED_HEADINGS = ("Concepts", "Sections")


# ---------------------------------------------------------------- containment / lock

def _contained(root_abs, candidate):
    """Real path of candidate iff it stays inside the bundle, else None.
    realpath (not abspath): a symlinked DIR inside the bundle must not
    smuggle operations outside it."""
    root_real = os.path.realpath(root_abs)
    real = os.path.realpath(candidate)
    return real if os.path.commonpath([root_real, real]) == root_real else None


def _ensure_bundle_gitignore(bundle_root):
    """Idempotently ensure `<bundle>/.gitignore` lists `.llm-wiki/` so transient state
    never lands in git. Twin of `_hook_common.ensure_bundle_gitignore` (duplicated here:
    bundle_ops also runs outside the hooks context). Best-effort — a failed hygiene write
    must never block the operation that triggered it."""
    gi = os.path.join(bundle_root, ".gitignore")
    try:
        existing = ""
        if os.path.isfile(gi):
            with open(gi, "r", encoding="utf-8") as fh:
                existing = fh.read()
            if any(l.strip() == ".llm-wiki/" for l in existing.split("\n")):
                return
            if not existing.endswith("\n"):
                existing += "\n"
        with open(gi, "w", encoding="utf-8") as fh:
            fh.write(existing + ".llm-wiki/\n")
    except OSError:
        pass


_HELD_LOCKS = set()  # realpaths of lock files this process already holds (flock deadlocks on re-open)


@contextmanager
def _bundle_lock(bundle_root):
    """Exclusive flock on `<bundle>/.llm-wiki/lock`, serializing concurrent writers
    (two `apply` processes racing the log.md read-modify-write). Reentrant within the
    process: apply holds it across its whole stage-commit section while the nested
    cmd_log_append re-enters. Creating the state dir carries the .gitignore guarantee."""
    state_dir = os.path.join(bundle_root, ".llm-wiki")
    os.makedirs(state_dir, exist_ok=True)
    _ensure_bundle_gitignore(bundle_root)
    lock_path = os.path.realpath(os.path.join(state_dir, "lock"))
    if lock_path in _HELD_LOCKS:
        yield
        return
    fh = open(lock_path, "a")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        _HELD_LOCKS.add(lock_path)
        try:
            yield
        finally:
            _HELD_LOCKS.discard(lock_path)
    finally:
        fh.close()  # closing the fd releases the flock


# ---------------------------------------------------------------- frontmatter

def _humanize(slug):
    return slug.replace("-", " ").replace("_", " ").strip().title()


# ------------------------------------------------------- v0.1 -> v0.2 migration

# The actor recorded when migrating a legacy concept. The producing model was never stored in
# v0.1 frontmatter, so claiming a specific one would fabricate provenance; `llm-wiki/unknown`
# is the honest `<producer>/<version>` form for "written by llm-wiki, model unrecorded".
MIGRATION_ACTOR = "llm-wiki/unknown"
_LEGACY_TS_RE = re.compile(r"^(timestamp|verified):[ \t]*(\S.*?)[ \t]*$")


def migrate_legacy_frontmatter(text):
    """Rewrite a concept's superseded v0.1 fields to their v0.2 shape (§13.1).

    `timestamp: X` -> `generated: { by, at: X }`; a bare scalar `verified: X` -> a
    `{ by, at: X }` mapping. Only top-level frontmatter keys are touched, so a nested
    `timestamp` inside a `sources` entry and every body line survive verbatim. Returns
    (text, changed). A body `Citations` list is deliberately NOT converted: free-text
    citations don't map mechanically onto `sources` entries, so R9 keeps warning instead
    of the engine guessing structure it can't recover."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return text, False
    close = next((n for n in range(1, len(lines)) if lines[n].rstrip() == "---"), None)
    if close is None:
        return text, False

    status, fm = _doctor.parse_frontmatter(text)
    if status != _doctor.OK:
        return text, False  # unparseable: the Doctor reports R1; never guess at a rewrite
    has_generated = isinstance(fm.get("generated"), dict)

    out, changed = [], False
    for n, line in enumerate(lines):
        if not (1 <= n < close):
            out.append(line)
            continue
        match = _LEGACY_TS_RE.match(line)  # anchored at column 0: top-level keys only
        if not match:
            out.append(line)
            continue
        key, value = match.group(1), match.group(2)
        if key == "timestamp":
            # An explicit `generated` is authoritative — drop the legacy duplicate.
            if not has_generated:
                out.append("generated: { by: %s, at: %s }" % (MIGRATION_ACTOR, value))
            changed = True
            continue
        if value.startswith("{") or value.startswith("["):
            out.append(line)  # already a v0.2 mapping/list on one line
            continue
        out.append("verified: { by: %s, at: %s }" % (MIGRATION_ACTOR, value))
        changed = True
    return "\n".join(out), changed


def stamp_generated_if_absent(text, actor, at):
    """Guarantee a §5.2 `generated: { by, at }` on a concept about to be written.

    Insert-only: a `generated` already in the content is authoritative (the publication path
    stamps one with the model it actually ran, which is better information than this default).
    Code owns `at` because a drafting model cannot reliably know the current instant."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return text  # no frontmatter: doctor reports R1; never invent a block
    close = next((n for n in range(1, len(lines)) if lines[n].rstrip() == "---"), None)
    if close is None:
        return text
    status, fm = _doctor.parse_frontmatter(text)
    if status != _doctor.OK or "generated" in (fm or {}):
        return text
    lines.insert(close, "generated: { by: %s, at: %s }" % (actor, at))
    return "\n".join(lines)


def migrate_bundle(bundle_root):
    """Migrate every concept in the bundle to v0.2 field shape. Returns the relpaths changed.
    Reserved files are skipped: the root index's `okf_version` is rewritten by the index
    regeneration that follows, and log.md carries no frontmatter."""
    changed = []
    for root, _dirs, files in os.walk(bundle_root):
        for name in sorted(files):
            if not name.endswith(".md") or name in ("index.md", "log.md"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue  # doctor reports unreadable/non-UTF-8 files; don't fail the write
            updated, did = migrate_legacy_frontmatter(text)
            if not did:
                continue
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(updated)
            changed.append(os.path.relpath(path, bundle_root).replace(os.sep, "/"))
    return changed


# ---------------------------------------------------------------- index regen

def _concept_meta(abspath):
    with open(abspath, "r", encoding="utf-8") as fh:
        text = fh.read()
    if text.startswith("﻿"):
        text = text[1:]  # strip a leading UTF-8 BOM (doctor.validate strips it pre-parse too)
    status, fm = _doctor.parse_frontmatter(text)
    if status != _doctor.OK:
        fm = {}  # unparseable frontmatter -> slug fallbacks; the Doctor reports it (R1)
    slug = os.path.basename(abspath)[:-3]
    title, desc = fm.get("title"), fm.get("description", "")
    return {
        "slug": slug,
        # doctor's parser can yield block lists; title/description are scalar-only here
        "title": title if isinstance(title, str) and title else _humanize(slug),
        "description": desc if isinstance(desc, str) else "",
    }


def _bullet(title, url, description):
    line = "* [%s](%s)" % (title, url)
    if description:
        line += " — %s" % description
    return line


def _split_preamble(text):
    """Return the preamble string — everything up to but excluding the first `## ` heading.
    That managed tail is discarded and rebuilt by the generator."""
    out = []
    for line in text.split("\n"):
        if line.startswith("## "):
            break
        out.append(line)
    # trim trailing blank lines from the preamble; the generator re-adds spacing
    while out and out[-1].strip() == "":
        out.pop()
    return "\n".join(out)


def _strip_leading_frontmatter(text):
    """Drop a leading `---`…`---` block (and the blank lines after it), returning the
    body. The generator owns index frontmatter, so any existing block is discarded and
    re-emitted per the rule — never preserved verbatim (else stray keys would survive)."""
    lines = text.split("\n")
    if lines and lines[0].rstrip() == "---":
        for i in range(1, len(lines)):
            if lines[i].rstrip() == "---":
                rest = lines[i + 1:]
                while rest and rest[0].strip() == "":
                    rest.pop(0)
                return "\n".join(rest)
    return text


def _dropped_headings(text):
    """Non-managed `## ` headings in an existing index.md whose content the regen
    discards (the managed Concepts/Sections tail is rebuilt, so it isn't a loss)."""
    out = []
    for line in _strip_leading_frontmatter(text).split("\n"):
        if line.startswith("## ") and line[3:].strip() not in MANAGED_HEADINGS:
            out.append(line[3:].strip())
    return out


def _render_index(dir_abs, bundle_root, concepts, subdirs):
    is_root = os.path.abspath(dir_abs) == os.path.abspath(bundle_root)
    title = _humanize(os.path.basename(os.path.abspath(dir_abs)))
    existing = os.path.join(dir_abs, "index.md")
    if os.path.isfile(existing):
        with open(existing, "r", encoding="utf-8") as fh:
            raw = fh.read()
        rel = os.path.relpath(existing, bundle_root).replace(os.sep, "/")
        for h in _dropped_headings(raw):
            sys.stderr.write(
                "warning: index regen drops hand-written section '## %s' in %s "
                "(move it above the first `## ` heading to keep it)\n" % (h, rel))
        body = _strip_leading_frontmatter(_split_preamble(raw)).strip("\n")
        if not body.strip():
            body = "# %s" % title
    else:
        body = "# %s" % title
    # frontmatter is generator-owned: root carries only okf_version; subdirs carry none
    preamble = (_ROOT_FRONTMATTER + body) if is_root else body
    parts = [preamble, ""]
    parts.append("## Concepts")
    parts.append("")
    if concepts:
        for c in concepts:
            parts.append(_bullet(c["title"], "./%s.md" % c["slug"], c["description"]))
    else:
        parts.append("_No concepts yet._")
    if subdirs:
        parts.append("")
        parts.append("## Sections")
        parts.append("")
        for name in subdirs:
            parts.append(_bullet(_humanize(name), "./%s/index.md" % name, ""))
    return "\n".join(parts).rstrip("\n") + "\n"


def _dirs_with_content(bundle_root):
    """Map each directory -> (concept abspaths, subdir names with content), for every
    directory that holds concepts or has a descendant that does."""
    concepts = {}   # dir_abs -> [concept abspaths]
    for root, _dirs, files in os.walk(bundle_root):
        cs = sorted(os.path.join(root, f) for f in files
                    if f.endswith(".md") and f not in RESERVED)
        if cs:
            concepts[os.path.abspath(root)] = cs
    # a directory is "live" if it or any descendant has concepts
    live = set()
    for d in concepts:
        cur = d
        root_abs = os.path.abspath(bundle_root)
        while True:
            live.add(cur)
            if cur == root_abs:
                break
            cur = os.path.dirname(cur)
    result = {}
    for d in sorted(live):
        cs = [_concept_meta(p) for p in concepts.get(d, [])]
        cs.sort(key=lambda c: (c["title"].lower(), c["slug"]))
        subs = sorted(name for name in os.listdir(d)
                      if os.path.isdir(os.path.join(d, name))
                      and os.path.abspath(os.path.join(d, name)) in live)
        result[d] = (cs, subs)
    return result


def _dirs_with_index(bundle_root):
    """Absolute paths of every directory that currently holds an index.md."""
    out = []
    for root, _dirs, files in os.walk(bundle_root):
        if "index.md" in files:
            out.append(os.path.abspath(root))
    return out


def cmd_index(bundle_root):
    try:
        live = _dirs_with_content(bundle_root)
    except OSError as e:
        sys.stderr.write("error: cannot read a concept file: %s\n" % e)
        return 2
    # Always (re)write the root index and any directory that currently HAS an index.md
    # — even one that just dropped to zero concepts — so a removed concept's stale
    # bullet disappears instead of lingering. (The dir itself is left for prune to rmdir.)
    targets = dict(live)
    for d in _dirs_with_index(bundle_root):
        if d not in targets:
            targets[d] = ([], [])  # has an index but no live content: emit an empty one
    root_abs = os.path.abspath(bundle_root)
    if root_abs not in targets:
        targets[root_abs] = ([], [])
    for d, (concepts, subdirs) in targets.items():
        content = _render_index(d, bundle_root, concepts, subdirs)
        with open(os.path.join(d, "index.md"), "w", encoding="utf-8") as fh:
            fh.write(content)
    return 0


# ---------------------------------------------------------------- log append

def cmd_log_append(bundle_root, kind, message, day):
    # the whole read-modify-write runs under the bundle lock so two concurrent
    # writers cannot each read the same log.md and drop the other's bullet
    with _bundle_lock(bundle_root):
        log_path = os.path.join(bundle_root, "log.md")
        bullet = "* **%s**: %s" % (kind, message)
        heading = "## %s" % day
        try:
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8") as fh:
                    lines = fh.read().split("\n")
            else:
                lines = ["# Directory Update Log", ""]
        except OSError as e:
            sys.stderr.write("error: cannot read log.md: %s\n" % e)
            return 2

        # parse the existing date headings (line index + ISO date), in document order
        headings = []
        for i, l in enumerate(lines):
            if l.startswith("## "):
                try:
                    headings.append((i, date.fromisoformat(l[3:].strip())))
                except ValueError:
                    pass  # malformed heading — leave it for the Doctor to flag
        target = date.fromisoformat(day)
        exact = next((i for i, d in headings if d == target), None)
        if exact is not None:
            # merge into the existing same-date section, after any blank line below it
            j = exact + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            lines.insert(j, bullet)
        else:
            # insert a fresh section before the first older-dated heading (keeps
            # newest-first); if none is older, append at the end
            older = next((i for i, d in headings if d < target), None)
            insert_at = older if older is not None else len(lines)
            lines[insert_at:insert_at] = [heading, "", bullet, ""]
        text = "\n".join(lines)
        if not text.endswith("\n"):
            text += "\n"
        try:
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as e:
            sys.stderr.write("error: cannot write log.md: %s\n" % e)
            return 2
        return 0


# ---------------------------------------------------------------- move

def _resolve(url, base_dir, bundle_root):
    if url.startswith("/"):
        return os.path.normpath(os.path.join(bundle_root, url.lstrip("/")))
    return os.path.normpath(os.path.join(base_dir, url))


def _rellink(target_abs, from_dir):
    rel = os.path.relpath(target_abs, from_dir).replace(os.sep, "/")
    return rel if rel.startswith(".") else "./" + rel


def _split_url(raw):
    """Split a markdown link payload into (url, suffix, bracketed). Handles the
    `<url>`, `url "title"` and bare `url` forms the same way doctor.py reads them, so
    move rewrites only the URL and re-emits the title/brackets verbatim. The full
    payload reconstructs as ("<"+url+">" if bracketed else url) + suffix."""
    if raw.startswith("<") and ">" in raw:
        end = raw.index(">")
        return raw[1:end], raw[end + 1:], True
    parts = raw.split(None, 1)
    if not parts:
        return "", "", False
    return parts[0], (" " + parts[1] if len(parts) > 1 else ""), False


def _inline_code_spans(line):
    """Return (start, end) char ranges covered by inline-code backtick spans on a line.
    A run of N backticks opens a span closed by the next run of exactly N (CommonMark);
    link-shaped text inside such a span must not be rewritten."""
    runs = [(m.start(), m.end()) for m in BACKTICK_RUN_RE.finditer(line)]
    spans, k = [], 0
    while k < len(runs):
        o_start, o_end = runs[k]
        n = o_end - o_start
        j = k + 1
        while j < len(runs) and (runs[j][1] - runs[j][0]) != n:
            j += 1
        if j < len(runs):
            spans.append((o_start, runs[j][1]))
            k = j + 1
        else:
            k += 1
    return spans


def _rewrite_links(text, file_old_abs, file_new_abs, old_abs, new_abs, bundle_root):
    """Rewrite links in one file's text. `old_abs`/`new_abs` are the moved concept's
    pre/post paths; `file_old_abs`/`file_new_abs` are this file's own pre/post paths
    (equal unless this file is the one being moved). Link-shaped text inside fenced
    (```/~~~) code blocks or inline-code (`…`) spans is documentation, not a real link,
    so it is left verbatim. Processed line-by-line (splitting on "\\n" preserves any
    CRLFs, which ride along as a trailing "\\r" on each segment).
    Decision of record: BOTH the `./`-relative and `/`-bundle-relative link forms are
    handled on purpose — robustness for foreign bundles that use either convention."""
    moved_self = file_old_abs != file_new_abs
    old_dir, new_dir = os.path.dirname(file_old_abs), os.path.dirname(file_new_abs)

    def repl_line(line, code_spans):
        def repl(m):
            if any(s <= m.start() < e for s, e in code_spans):
                return m.group(0)          # inside an inline-code span — leave verbatim
            pre, raw, post = m.group(1), m.group(2), m.group(3)
            url, suffix, bracketed = _split_url(raw)
            base, _, frag = url.partition("#")
            if (not base or base.startswith("#")
                    or base.lower().startswith(EXTERNAL_SCHEMES)):
                return m.group(0)
            is_bundle = base.startswith("/")
            resolved = _resolve(base, old_dir, bundle_root)
            if resolved == old_abs:
                target_abs = new_abs       # link points at the moved concept
            elif moved_self:
                target_abs = resolved      # link rides along inside the moved file
            else:
                return m.group(0)          # unaffected
            new_url = ("/" + os.path.relpath(target_abs, bundle_root).replace(os.sep, "/")
                       if is_bundle else _rellink(target_abs, new_dir))
            if frag:
                new_url += "#" + frag
            payload = ("<%s>" % new_url if bracketed else new_url) + suffix
            return pre + payload + post
        return LINK_RE.sub(repl, line)

    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)               # fence delimiter — never rewritten
        elif in_fence:
            out.append(line)               # inside a fenced block — leave verbatim
        else:
            out.append(repl_line(line, _inline_code_spans(line)))
    return "\n".join(out)


def cmd_move(bundle_root, src_rel, dst_rel):
    old_abs = os.path.normpath(os.path.join(bundle_root, src_rel))
    new_abs = os.path.normpath(os.path.join(bundle_root, dst_rel))
    root_abs = os.path.abspath(bundle_root)
    for p in (old_abs, new_abs):
        if _contained(root_abs, p) is None:
            sys.stderr.write("error: path escapes the bundle: %s\n" % p)
            return 2
    if not os.path.isfile(old_abs):
        sys.stderr.write("error: source concept not found: %s\n" % src_rel)
        return 2
    if os.path.basename(old_abs) in RESERVED or os.path.basename(new_abs) in RESERVED:
        sys.stderr.write("error: move operates on concepts, not reserved files\n")
        return 2
    if os.path.exists(new_abs):
        # A pure case-only rename (Foo.md -> foo.md) resolves to the same inode on a
        # case-insensitive FS (macOS APFS default), so the existence check fires on the
        # source itself; allow it when src/dst differ only by case and are the same file.
        case_only = (old_abs.lower() == new_abs.lower() and old_abs != new_abs
                     and os.path.samefile(old_abs, new_abs))
        if not case_only:
            sys.stderr.write("error: destination already exists: %s\n" % dst_rel)
            return 2

    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    os.rename(old_abs, new_abs)

    for root, _dirs, files in os.walk(bundle_root):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            fabs = os.path.normpath(os.path.join(root, fn))
            file_new = fabs
            file_old = old_abs if fabs == new_abs else fabs
            # newline="" disables newline translation so only the link text changes;
            # a CRLF referrer keeps its CRLFs instead of being collapsed to LF.
            with open(fabs, "r", encoding="utf-8", newline="") as fh:
                text = fh.read()
            updated = _rewrite_links(text, file_old, file_new, old_abs, new_abs, bundle_root)
            if updated != text:
                with open(fabs, "w", encoding="utf-8", newline="") as fh:
                    fh.write(updated)
    return 0


def cmd_remove(bundle_root, rel):
    root_abs = os.path.abspath(bundle_root)
    abspath = os.path.normpath(os.path.join(root_abs, rel))
    if os.path.basename(abspath) in RESERVED:
        sys.stderr.write("error: remove operates on concepts, not reserved files\n")
        return 2
    if _contained(root_abs, abspath) is None:
        sys.stderr.write("error: path escapes the bundle: %s\n" % rel)
        return 2
    if not os.path.isfile(abspath):
        sys.stderr.write("error: concept not found: %s\n" % rel)
        return 2
    os.remove(abspath)
    return 0


# ---------------------------------------------------------------- apply (gated write)

# Deterministic seed title for an auto-initialized bundle. A constant (not the dir's
# basename) keeps auto-init reproducible — _render_index falls back to the humanized
# basename only when the index has no preamble body, which a random tmp dir would make
# non-deterministic; cmd_index preserves this heading on every later regen.
INIT_TITLE = "# Knowledge"


def _init_empty_bundle(bundle_root, day):
    """Create a conformant empty bundle in place if index.md/log.md are absent.
    A bare `# Directory Update Log` fails Doctor R3c (no date section), so the log is
    seeded with an Initialization entry via the engine — matching the
    log-is-never-hand-authored convention. Idempotent: an existing file is left alone."""
    _ensure_bundle_gitignore(bundle_root)
    idx = os.path.join(bundle_root, "index.md")
    if not os.path.isfile(idx):
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write("%s%s\n" % (_ROOT_FRONTMATTER, INIT_TITLE))
    if not os.path.isfile(os.path.join(bundle_root, "log.md")):
        cmd_log_append(bundle_root, "Initialization", "Bundle created.", day)


def _build(bundle_root, concept_rel, content, kind, message, day, actor=None, at=None):
    """Write the concept bytes at <relpath>, regenerate the index, append the log entry.
    The single place the three deterministic ops compose for one capture; run identically
    against the throwaway mirror (gating) and the live bundle (commit)."""
    dest = os.path.normpath(os.path.join(bundle_root, concept_rel))
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if actor:
        content = stamp_generated_if_absent(
            content.decode("utf-8"), actor, at).encode("utf-8")
    with open(dest, "wb") as fh:
        fh.write(content)
    rc = _migrate_and_log(bundle_root, day)
    if rc != 0:
        return rc
    rc = cmd_index(bundle_root)
    if rc != 0:
        return rc
    return cmd_log_append(bundle_root, kind, message, day)


def _migrate_and_log(bundle_root, day):
    """Bring any legacy v0.1 concepts up to v0.2 shape, recording it once in log.md.
    Runs inside the same staged-mirror-then-commit flow as the write itself, so the
    migrated bytes are Doctor-gated before they land and are equally git-reversible."""
    changed = migrate_bundle(bundle_root)
    if not changed:
        return 0
    sys.stderr.write("migrated %d concept(s) to OKF v%s field shape\n"
                     % (len(changed), _doctor.OKF_VERSION))
    return cmd_log_append(
        bundle_root, "Update",
        "Migrated %d concept(s) to OKF v%s frontmatter (`timestamp` -> `generated`, "
        "scalar `verified` -> `{ by, at }`)." % (len(changed), _doctor.OKF_VERSION),
        day,
    )


def cmd_apply(bundle_root, concept_rel, content_file, kind, message, day, actor=None):
    """Consolidated gated write: stage on a /tmp mirror, regenerate index + log,
    Doctor-gate (strict) and secret-scan; only on a clean gate is the LIVE bundle
    touched — re-built against the live tree, git-reversible. The whole stage-commit
    section runs under the bundle flock so concurrent applies serialize instead of
    racing the log.md read-modify-write. A block leaves the live bundle's concepts/
    index/log byte-for-byte untouched (only the gitignored `.llm-wiki/` lock state
    may appear). Emits a one-line JSON status to stdout
    (applied | blocked:doctor | blocked:secret | error:post-commit)."""
    root_abs = os.path.abspath(bundle_root)
    dest_abs = os.path.normpath(os.path.join(root_abs, concept_rel))
    if os.path.basename(dest_abs) in RESERVED:
        sys.stderr.write("error: apply operates on concepts, not reserved files\n")
        return 2
    if not dest_abs.endswith(".md"):
        sys.stderr.write("error: --concept must be a .md path\n")
        return 2
    if _contained(root_abs, dest_abs) is None:
        sys.stderr.write("error: path escapes the bundle: %s\n" % concept_rel)
        return 2
    try:
        with open(content_file, "rb") as fh:
            content = fh.read()
    except OSError as e:
        sys.stderr.write("error: cannot read content file: %s\n" % e)
        return 2

    # Upsert: default the log kind by whether the concept already exists; callers
    # (capture / wiki-capturer) normally pass an explicit kind + message.
    if kind is None:
        kind = "Update" if os.path.isfile(dest_abs) else "Creation"
    if kind not in ("Creation", "Update", "Initialization"):
        sys.stderr.write("error: --log-kind must be Creation|Update|Initialization\n")
        return 2
    if message is None:
        message = "Captured `%s`." % concept_rel.replace(os.sep, "/")

    # One instant for both the staged and the committed build, so the gated bytes and the
    # bytes that land are identical.
    stamped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    mirror = tempfile.mkdtemp(prefix="llm-wiki-apply-")
    try:
        # The flock spans staging AND commit: staging's copytree must snapshot a
        # settled live bundle, and the commit rebuild must not interleave with a
        # concurrent apply's (both would read-modify-write the same log.md).
        with _bundle_lock(root_abs):
            # --- stage on the throwaway mirror; the live bundle is NOT touched here ---
            if os.path.isdir(root_abs):
                shutil.copytree(root_abs, mirror, dirs_exist_ok=True)
            _init_empty_bundle(mirror, day)
            rc = _build(mirror, concept_rel, content, kind, message, day, actor, stamped_at)
            if rc != 0:
                sys.stderr.write("error: staging failed (exit %d)\n" % rc)
                return 2

            _r, _n, findings = _doctor.validate(mirror)
            errors = [f for f in findings if f["severity"] == "ERROR"]
            if errors:
                sys.stderr.write("doctor blocked apply (%d error(s)):\n" % len(errors))
                for f in errors:
                    sys.stderr.write("ERROR %s %s:%d   %s\n"
                                     % (f["rule"], f["file"], f["line"], f["message"]))
                print(json.dumps({"status": "blocked:doctor", "concept": concept_rel,
                                  "errors": len(errors)}))
                return 1

            # Scan every input channel apply commits, not just the body: the log message
            # lands in log.md and the concept path lands in index.md, both unscanned otherwise.
            # (Title/description derive from content, already scanned.) Do NOT scan staged
            # files — a grandfathered secret elsewhere must not block an unrelated apply.
            sfindings = []
            for channel, text in (("content", content.decode("utf-8", "replace")),
                                  ("log-message", message), ("concept-path", concept_rel)):
                for f in _secret_scan.scan(text):
                    sfindings.append((channel, f))
            if sfindings:
                sys.stderr.write("secret scan blocked apply (%d finding(s)):\n" % len(sfindings))
                for channel, f in sfindings:
                    sys.stderr.write("SECRET %s %s line %d preview=%s\n"
                                     % (channel, f["category"], f["line"], f["preview"]))
                print(json.dumps({"status": "blocked:secret", "concept": concept_rel,
                                  "findings": len(sfindings)}))
                return 1

            # --- commit: only now (gates clean) is the live bundle mutated ---
            os.makedirs(root_abs, exist_ok=True)
            _init_empty_bundle(root_abs, day)
            rc = _build(root_abs, concept_rel, content, kind, message, day, actor, stamped_at)
            if rc != 0:
                sys.stderr.write("error: commit failed (exit %d)\n" % rc)
                return 2
            _r2, _n2, lfind = _doctor.validate(root_abs)
            lerr = [f for f in lfind if f["severity"] == "ERROR"]
            if lerr:
                sys.stderr.write("error: post-commit Doctor failed unexpectedly:\n")
                for f in lerr:
                    sys.stderr.write("ERROR %s %s:%d   %s\n"
                                     % (f["rule"], f["file"], f["line"], f["message"]))
                print(json.dumps({"status": "error:post-commit", "concept": concept_rel,
                                  "hint": "live bundle mutated and failed validation - "
                                          "restore with: git checkout -- %s" % root_abs}))
                return 1
            print(json.dumps({"status": "applied", "concept": concept_rel}))
            return 0
    finally:
        shutil.rmtree(mirror, ignore_errors=True)


def _load_batch_manifest(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("cannot read batch manifest: %s" % exc) from exc
    if not isinstance(value, dict) or not isinstance(value.get("concepts"), list):
        raise ValueError("batch manifest concepts must be a list")
    for field, expected in (
        ("project", str), ("expected_head", str), ("expected_source_hashes", dict),
        ("expected_destinations", dict),
    ):
        if not isinstance(value.get(field), expected):
            raise ValueError("batch manifest %s has the wrong type" % field)
    if not 1 <= len(value["concepts"]) <= 40:
        raise ValueError("batch manifest must contain 1..40 concepts")
    message = value.get("log_message")
    if not isinstance(message, str) or not message.strip() or "\n" in message or "\r" in message:
        raise ValueError("batch log_message must be one non-empty line")
    return value


def _validated_batch(root_abs, manifest):
    concepts, seen = [], set()
    for index, item in enumerate(manifest["concepts"]):
        if not isinstance(item, dict):
            raise ValueError("batch concept %d must be an object" % index)
        rel, content = item.get("path"), item.get("content")
        if not isinstance(rel, str) or not rel.endswith(".md"):
            raise ValueError("batch concept %d has an invalid .md path" % index)
        dest = os.path.normpath(os.path.join(root_abs, rel))
        canonical = os.path.relpath(dest, root_abs).replace(os.sep, "/")
        if (
            os.path.basename(dest) in RESERVED
            or _contained(root_abs, dest) is None
            or rel.replace("\\", "/") != canonical
            or canonical in seen
        ):
            raise ValueError("batch concept path is reserved, duplicate, or escapes: %s" % rel)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("batch concept %s has empty content" % rel)
        seen.add(canonical)
        concepts.append((canonical, content.encode("utf-8")))
    return concepts


def _absolute_hash(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return "sha256:" + digest.hexdigest()


def _git_head(project):
    try:
        proc = subprocess.run(
            ["git", "-C", project, "rev-parse", "HEAD"], capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unborn"
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unborn"


def _batch_preflight(root_abs, manifest, concepts):
    project = os.path.realpath(manifest["project"])
    if not os.path.isdir(project) or _git_head(project) != manifest["expected_head"]:
        return "repository HEAD changed"
    for source, expected in manifest["expected_source_hashes"].items():
        if not isinstance(source, str) or os.path.isabs(source) or ".." in source.replace("\\", "/").split("/"):
            return "source path is unsafe"
        if _absolute_hash(os.path.realpath(os.path.join(project, source))) != expected:
            return "source hash changed: %s" % source
    expected_destinations = manifest["expected_destinations"]
    if set(expected_destinations) != {rel for rel, _content in concepts}:
        return "destination preconditions do not match the batch"
    for rel, _content in concepts:
        if _absolute_hash(os.path.join(root_abs, rel)) != expected_destinations[rel]:
            return "destination changed: %s" % rel
    return None


def _build_batch(bundle_root, concepts, message, day):
    for rel, content in concepts:
        dest = os.path.normpath(os.path.join(bundle_root, rel))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as handle:
            handle.write(content)
    rc = _migrate_and_log(bundle_root, day)
    if rc != 0:
        return rc
    rc = cmd_index(bundle_root)
    return rc if rc else cmd_log_append(bundle_root, "Creation", message, day)


def cmd_batch_apply(bundle_root, manifest_file, day):
    root_abs = os.path.abspath(bundle_root)
    try:
        manifest = _load_batch_manifest(manifest_file)
        concepts = _validated_batch(root_abs, manifest)
    except ValueError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    message = manifest["log_message"]
    mirror = tempfile.mkdtemp(prefix="llm-wiki-batch-")
    backup = tempfile.mkdtemp(prefix="llm-wiki-batch-backup-")
    try:
        with _bundle_lock(root_abs):
            stale = _batch_preflight(root_abs, manifest, concepts)
            if stale:
                print(json.dumps({"status": "stale-result", "reason": stale}))
                return 3
            if os.path.isdir(root_abs):
                shutil.copytree(root_abs, mirror, dirs_exist_ok=True)
            _init_empty_bundle(mirror, day)
            rc = _build_batch(mirror, concepts, message, day)
            if rc:
                sys.stderr.write("error: batch staging failed (exit %d)\n" % rc)
                return 2
            _r, _n, findings = _doctor.validate(mirror)
            errors = [finding for finding in findings if finding["severity"] == "ERROR"]
            if errors:
                print(json.dumps({"status": "blocked:doctor", "errors": len(errors)}))
                return 1
            secret_findings = []
            channels = [("log-message", message)]
            for rel, content in concepts:
                channels.extend((("concept-path", rel), ("content", content.decode("utf-8", "replace"))))
            for channel, text in channels:
                for finding in _secret_scan.scan(text):
                    secret_findings.append((channel, finding))
            if secret_findings:
                print(json.dumps({"status": "blocked:secret", "findings": len(secret_findings)}))
                return 1

            existed = os.path.isdir(root_abs)
            if existed:
                shutil.copytree(root_abs, backup, dirs_exist_ok=True)
            try:
                os.makedirs(root_abs, exist_ok=True)
                _init_empty_bundle(root_abs, day)
                rc = _build_batch(root_abs, concepts, message, day)
            except OSError as exc:
                rc = 2
                sys.stderr.write("error: batch commit failed: %s\n" % exc)
            if rc:
                shutil.rmtree(root_abs, ignore_errors=True)
                if existed:
                    shutil.copytree(backup, root_abs)
                return 2
            try:
                _r2, _n2, live_findings = _doctor.validate(root_abs)
            except (OSError, UnicodeError, ValueError) as exc:
                shutil.rmtree(root_abs, ignore_errors=True)
                if existed:
                    shutil.copytree(backup, root_abs)
                sys.stderr.write("error: post-commit validation failed; batch rolled back: %s\n" % exc)
                return 2
            live_errors = [finding for finding in live_findings if finding["severity"] == "ERROR"]
            if live_errors:
                shutil.rmtree(root_abs, ignore_errors=True)
                if existed:
                    shutil.copytree(backup, root_abs)
                print(json.dumps({"status": "error:post-commit", "errors": len(live_errors)}))
                return 1
            print(json.dumps({
                "status": "applied", "concepts": [rel for rel, _content in concepts]
            }))
            return 0
    finally:
        shutil.rmtree(mirror, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


# ---------------------------------------------------------------- linkcheck

def cmd_stage(bundle_root):
    """Stage the bundle's current git state atomically w.r.t. `apply`: `git add -A` scoped to
    the bundle directory, under the bundle flock. Without the lock a foreground `git add` can
    interleave with a background Scribe apply and commit an index/log that references a concept
    file the commit doesn't include (an R4 broken link). `.llm-wiki/` transient state is
    gitignored, so the bundle-scoped `-A` stays safe."""
    root_abs = os.path.abspath(bundle_root)
    with _bundle_lock(root_abs):
        try:
            proc = subprocess.run(
                ["git", "-C", root_abs, "add", "-A", "--", "."],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            sys.stderr.write("error: git add failed: %s\n" % e)
            return 2
    if proc.returncode != 0:
        sys.stderr.write("error: git add failed (exit %d): %s\n"
                         % (proc.returncode, proc.stderr.strip()))
        return 2
    print(json.dumps({"status": "staged", "bundle": bundle_root}))
    return 0


def cmd_linkcheck(bundle_root):
    """Report every internal markdown link in the bundle (skipping `.llm-wiki/`) as
    {"status": "ok", "links": [...]} — same regex/fence/image/scheme handling as
    doctor.check_links, but exhaustive (every link, with an `exists` bool) instead of
    broken-only. Report-only: exit 0 even when links are broken."""
    root_abs = os.path.abspath(bundle_root)
    md_paths = []
    for root, dirs, files in os.walk(root_abs):
        dirs[:] = [d for d in dirs if d != ".llm-wiki"]
        for fn in files:
            if fn.endswith(".md"):
                md_paths.append(os.path.join(root, fn))
    links = []
    for p in sorted(md_paths):
        rel = os.path.relpath(p, root_abs).replace(os.sep, "/")
        try:
            with open(p, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write("error: cannot read %s: %s\n" % (rel, e))
            return 2
        base = os.path.dirname(p)
        in_fence = False
        for n, line in enumerate(text.split("\n"), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue  # links inside a ``` example are documentation, not real cross-links
            for m in _doctor.LINK_RE.finditer(line):
                # `![alt](src)` is an image embed, not a concept link — skip the image tail.
                if m.start() > 0 and line[m.start() - 1] == "!":
                    continue
                raw = m.group(1).strip()
                # markdown allows `(<url> "title")`; take the URL part only
                if raw.startswith("<") and ">" in raw:
                    target = raw[1:raw.index(">")]
                else:
                    target = raw.split()[0] if raw.split() else ""
                if not target or target.startswith("#"):
                    continue
                if target.lower().startswith(EXTERNAL_SCHEMES):
                    continue
                path_part = target.split("#", 1)[0].split("?", 1)[0]
                if not path_part:
                    continue  # was a pure fragment
                if path_part.startswith("/"):
                    resolved_abs = os.path.join(root_abs, path_part.lstrip("/"))
                else:
                    resolved_abs = os.path.join(base, path_part)
                resolved_abs = os.path.normpath(resolved_abs)
                exists = (os.path.isdir(resolved_abs) if path_part.endswith("/")
                          else os.path.isfile(resolved_abs))
                links.append({
                    "file": rel,
                    "line": n,
                    "raw": target,
                    "resolved": os.path.relpath(resolved_abs, root_abs).replace(os.sep, "/"),
                    "exists": exists,
                })
    print(json.dumps({"status": "ok", "links": links}))
    return 0


# ---------------------------------------------------------------- merge

def _has_conflict(text):
    return any(l.startswith("<<<<<<< ") for l in text.split("\n"))


def _split_conflict(text):
    """Resolve standard git conflict markers into the two full sides (ours, theirs).
    Lines outside a conflict hunk are common to both; `=======` only counts as a
    separator while inside a hunk (a setext underline elsewhere is left alone)."""
    ours, theirs = [], []
    state = 0  # 0 = common, 1 = ours hunk, 2 = theirs hunk
    for line in text.split("\n"):
        if line.startswith("<<<<<<< ") and state == 0:
            state = 1
        elif line.rstrip() == "=======" and state == 1:
            state = 2
        elif line.startswith(">>>>>>> ") and state == 2:
            state = 0
        elif state == 1:
            ours.append(line)
        elif state == 2:
            theirs.append(line)
        else:
            ours.append(line)
            theirs.append(line)
    return "\n".join(ours), "\n".join(theirs)


def _parse_log_side(text):
    """Parse one side of log.md with the same grammar doctor.check_log enforces:
    fence-aware, `## YYYY-MM-DD` H2 date headings, `* `/`- ` bullets under them.
    Returns (title_line_or_None, {date: [bullet lines]}). Bullets under a malformed
    heading (and any other stray prose) are dropped — the log is engine-authored, so
    grammar-only content is the invariant; the Doctor gate after merge reports gaps."""
    title, entries, cur, in_fence = None, {}, None, False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            if _doctor.DATE_RE.match(heading):
                try:
                    cur = date.fromisoformat(heading)
                    entries.setdefault(cur, [])
                    continue
                except ValueError:
                    pass
            cur = None
        elif (line.startswith("* ") or line.startswith("- ")) and cur is not None:
            entries[cur].append(line)
        elif title is None and line.startswith("# "):
            title = line
    return title, entries


def _merge_log_text(text):
    """Union-merge a conflicted log.md: both sides' bullets under their date headings,
    deduped byte-identical, dates newest-first, first-seen bullet order per date."""
    ours, theirs = _split_conflict(text)
    title_a, ent_a = _parse_log_side(ours)
    title_b, ent_b = _parse_log_side(theirs)
    merged = {}
    for ent in (ent_a, ent_b):
        for d, bullets in ent.items():
            lst = merged.setdefault(d, [])
            for b in bullets:
                if b not in lst:
                    lst.append(b)
    parts = [title_a or title_b or "# Directory Update Log", ""]
    for d in sorted(merged, reverse=True):
        parts.append("## %s" % d.isoformat())
        parts.append("")
        parts.extend(merged[d])
        parts.append("")
    while parts and parts[-1] == "":
        parts.pop()
    return "\n".join(parts) + "\n"


def cmd_merge(bundle_root):
    """Resolve git conflict markers in log.md (bullet union) and index.md files
    (conflicted content discarded — the regen below rebuilds them from frontmatter),
    then regenerate indexes unconditionally and Doctor-gate the result. A doctor block
    leaves the merged files in place so the caller can inspect them."""
    root_abs = os.path.abspath(bundle_root)
    log_path = os.path.join(root_abs, "log.md")
    resolved = []
    # merge is a writer too — the conflict scan, the log.md read, AND the rewrite all
    # run under one lock, so a concurrent apply/log-append cannot land a bullet between
    # the read and the stale-text rewrite (lost update)
    with _bundle_lock(root_abs):
        index_paths = []
        for root, dirs, files in os.walk(root_abs):
            dirs[:] = [d for d in dirs if d != ".llm-wiki"]
            if "index.md" in files:
                index_paths.append(os.path.normpath(os.path.join(root, "index.md")))
        try:
            log_text = None
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8") as fh:
                    log_text = fh.read()
            conflicted_indexes = []
            for p in sorted(index_paths):
                with open(p, "r", encoding="utf-8") as fh:
                    if _has_conflict(fh.read()):
                        conflicted_indexes.append(p)
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write("error: cannot read bundle file: %s\n" % e)
            return 2

        log_conflicted = log_text is not None and _has_conflict(log_text)
        if not log_conflicted and not conflicted_indexes:
            print(json.dumps({"status": "clean"}))
            return 0

        if log_conflicted:
            try:
                with open(log_path, "w", encoding="utf-8") as fh:
                    fh.write(_merge_log_text(log_text))
            except OSError as e:
                sys.stderr.write("error: cannot write log.md: %s\n" % e)
                return 2
            resolved.append("log.md")
        for p in conflicted_indexes:
            os.remove(p)  # discarded; the index regen below rebuilds it
            resolved.append(os.path.relpath(p, root_abs).replace(os.sep, "/"))
        rc = cmd_index(root_abs)
        if rc != 0:
            sys.stderr.write("error: index regeneration failed (exit %d)\n" % rc)
            return 2

    try:
        _r, _n, findings = _doctor.validate(root_abs)
    except ValueError as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    errors = [f for f in findings if f["severity"] == "ERROR"]
    if errors:
        print(json.dumps({"status": "blocked:doctor", "resolved": resolved,
                          "violations": errors,
                          "hint": "merged files were left in place for inspection - "
                                  "fix the violations and re-run doctor"}))
        return 1
    print(json.dumps({"status": "merged", "resolved": resolved}))
    return 0


# ---------------------------------------------------------------- cli

def _opt(argv, name):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def _bad_date(day):
    # a provided --date must parse; an absent one is defaulted downstream
    if not day:
        return False
    try:
        date.fromisoformat(day)
        return False
    except ValueError:
        return True


def main(argv):
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    sub, rest = argv[0], argv[1:]
    if not rest:
        sys.stderr.write("error: %s needs a bundle-root argument\n" % sub)
        return 2
    bundle_root = rest[0]
    # apply operations auto-initialize an absent bundle, so they tolerate a missing directory;
    # every other subcommand operates in place and requires the bundle to exist.
    if sub not in ("apply", "batch-apply") and not os.path.isdir(bundle_root):
        sys.stderr.write("error: not a directory: %s\n" % bundle_root)
        return 2

    if sub == "apply":
        concept = _opt(rest, "--concept")
        content_file = _opt(rest, "--content-file")
        if not concept:
            sys.stderr.write("error: apply requires --concept\n")
            return 2
        if not content_file:
            sys.stderr.write("error: apply requires --content-file\n")
            return 2
        kind, message, day = (_opt(rest, "--log-kind"), _opt(rest, "--log-message"),
                              _opt(rest, "--date"))
        if _bad_date(day):
            sys.stderr.write("error: --date must be an ISO date (YYYY-MM-DD)\n")
            return 2
        if not day:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # §7 actor for the `generated` stamp. Defaulted rather than required so an older
        # caller keeps working; callers that know their model should pass it.
        actor = _opt(rest, "--generated-by") or MIGRATION_ACTOR
        if not _doctor.ACTOR_RE.match(actor):
            sys.stderr.write("error: --generated-by must follow the OKF actor convention "
                             "(<producer>/<version>, human:<id>, process:<id>)\n")
            return 2
        return cmd_apply(bundle_root, concept, content_file, kind, message, day, actor)

    if sub == "batch-apply":
        manifest, day = _opt(rest, "--manifest"), _opt(rest, "--date")
        if not manifest:
            sys.stderr.write("error: batch-apply requires --manifest\n")
            return 2
        if _bad_date(day):
            sys.stderr.write("error: --date must be an ISO date (YYYY-MM-DD)\n")
            return 2
        if not day:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return cmd_batch_apply(bundle_root, manifest, day)

    if sub == "index":
        return cmd_index(bundle_root)
    if sub == "log-append":
        kind, message, day = _opt(rest, "--kind"), _opt(rest, "--message"), _opt(rest, "--date")
        if kind not in ("Creation", "Update", "Initialization"):
            sys.stderr.write("error: --kind must be Creation|Update|Initialization\n")
            return 2
        if not message:
            sys.stderr.write("error: --message is required\n")
            return 2
        if "\n" in message or "\r" in message:
            # a single log bullet is one line; an embedded newline either orphans a
            # paragraph (silent R3 corruption) or spawns a stray bullet (R3c fail).
            sys.stderr.write("error: --message must be a single line (no newlines)\n")
            return 2
        if _bad_date(day):
            sys.stderr.write("error: --date must be an ISO date (YYYY-MM-DD)\n")
            return 2
        if not day:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return cmd_log_append(bundle_root, kind, message, day)
    if sub == "move":
        src, dst = _opt(rest, "--from"), _opt(rest, "--to")
        if not src or not dst:
            sys.stderr.write("error: move requires --from and --to\n")
            return 2
        return cmd_move(bundle_root, src, dst)
    if sub == "remove":
        concept = _opt(rest, "--concept")
        if not concept:
            sys.stderr.write("error: remove requires --concept\n")
            return 2
        return cmd_remove(bundle_root, concept)
    if sub == "stage":
        return cmd_stage(bundle_root)
    if sub == "linkcheck":
        return cmd_linkcheck(bundle_root)
    if sub == "merge":
        return cmd_merge(bundle_root)

    sys.stderr.write("error: unknown subcommand: %s\n" % sub)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
