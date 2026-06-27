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
        `okf_version: "0.1"` frontmatter; subdir index.md gets zero frontmatter.

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
        per spec §5 broken links are tolerated, never silently rewritten away.

Exit codes: 0 ok; 2 usage / operational error.
"""
import os
import re
import sys
from datetime import date, datetime, timezone

LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)]+)(\))")
# A line opening/closing a fenced code block (``` or ~~~), toggled per-line so the
# link rewriter never mutates link-shaped text inside a fenced example (mirrors doctor.py).
FENCE_RE = re.compile(r"^(```|~~~)")
# A run of backticks delimiting an inline-code span; an opener is closed by the next
# run of EQUAL length (CommonMark), so link-shaped text inside `…` is left verbatim.
BACKTICK_RUN_RE = re.compile(r"`+")
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "ftp://", "tel:", "//")
RESERVED = ("index.md", "log.md")
MANAGED_HEADINGS = ("Concepts", "Sections")


# ---------------------------------------------------------------- frontmatter

def _parse_frontmatter(text):
    """Minimal reader: returns a dict of top-level `key: scalar` pairs (lists ignored).
    Mirrors doctor.py's restricted grammar enough to read title/description."""
    if text.startswith("﻿"):
        text = text[1:]  # strip a leading UTF-8 BOM (matches doctor.py)
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return {}
    close = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close = i
            break
    if close is None:
        return {}
    data = {}
    for line in lines[1:close]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m and m.group(2).strip():
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            data[m.group(1)] = v
    return data


def _humanize(slug):
    return slug.replace("-", " ").replace("_", " ").strip().title()


# ---------------------------------------------------------------- index regen

def _concept_meta(abspath):
    with open(abspath, "r", encoding="utf-8") as fh:
        fm = _parse_frontmatter(fh.read())
    slug = os.path.basename(abspath)[:-3]
    return {
        "slug": slug,
        "title": fm.get("title") or _humanize(slug),
        "description": fm.get("description", ""),
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
    preamble = ('---\nokf_version: "0.1"\n---\n%s' % body) if is_root else body
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
    CRLFs, which ride along as a trailing "\\r" on each segment)."""
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
        if os.path.commonpath([root_abs, os.path.abspath(p)]) != root_abs:
            sys.stderr.write("error: path escapes the bundle: %s\n" % p)
            return 2
    if not os.path.isfile(old_abs):
        sys.stderr.write("error: source concept not found: %s\n" % src_rel)
        return 2
    if os.path.basename(old_abs) in RESERVED or os.path.basename(new_abs) in RESERVED:
        sys.stderr.write("error: move operates on concepts, not reserved files\n")
        return 2
    if os.path.exists(new_abs):
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
    if os.path.commonpath([root_abs, abspath]) != root_abs:
        sys.stderr.write("error: path escapes the bundle: %s\n" % rel)
        return 2
    if not os.path.isfile(abspath):
        sys.stderr.write("error: concept not found: %s\n" % rel)
        return 2
    os.remove(abspath)
    return 0


# ---------------------------------------------------------------- cli

def _opt(argv, name):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def main(argv):
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    sub, rest = argv[0], argv[1:]
    if not rest:
        sys.stderr.write("error: %s needs a bundle-root argument\n" % sub)
        return 2
    bundle_root = rest[0]
    if not os.path.isdir(bundle_root):
        sys.stderr.write("error: not a directory: %s\n" % bundle_root)
        return 2

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

    sys.stderr.write("error: unknown subcommand: %s\n" % sub)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
