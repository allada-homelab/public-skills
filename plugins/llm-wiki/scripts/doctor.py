#!/usr/bin/env python3
"""OKF v0.1 conformance validator ("Doctor") for the /llm-wiki plugin.

Stdlib-only. Strict-producer mode is the pre-write gate for everything the plugin
authors; lenient-consumer mode (for reading foreign bundles) is a Phase 4 stub here.

Usage:
    doctor.py <bundle-dir-or-file> [--mode strict|lenient] [--format text|json]

Exit codes:
    0  validated, zero ERRORs (WARNINGs allowed)
    1  one or more ERRORs
    2  usage / operational error (bad path, bare index.md, --mode lenient, bad flag)

Rules (see docs/llm-wiki/phases/phase-1-tech-plan.md §5):
    R1   concept has parseable YAML frontmatter
    R2   concept frontmatter has a non-empty `type`
    R3a  subdirectory index.md has zero frontmatter
    R3b  root index.md frontmatter keys ⊆ {okf_version}, and okf_version == "0.1"
    R3c  log.md: ISO YYYY-MM-DD headings, newest-first, bold **Update/Creation/Initialization** bullets
    R4   internal markdown links resolve (WARNING only — broken links are tolerated per OKF spec §5)
    R5   concept `type` is in the canonical vocabulary (WARNING only — OKF §3 only requires a
         non-empty type; R5 is a curation nudge to keep grouping/analytics stable, never an ERROR)
"""
import json
import os
import re
import sys
from datetime import date

SCHEMA = "okf-doctor/1"
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
LIST_ITEM_RE = re.compile(r"^(\s*)-\s+(.*)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ATX_HEADING_RE = re.compile(r"^(#+)\s+(.*)$")
# A heading body that *looks like* a date — used to catch date headings placed at the wrong
# ATX level (H1/H3) where they'd otherwise skip the H2 date-section checks entirely.
DATE_CANDIDATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}\b")
LOG_PREFIXES = ("**Update**", "**Creation**", "**Initialization**")
# R5: the canonical concept-type vocabulary (matched case-insensitively). Lowercase single
# tokens (hyphens ok) are the house style; `bigquery table` is the one compound kept because it
# is OKF's own reference example type and is entrenched in the fixture corpus. Widening the set
# beats warning on (and thus rewriting) the frozen example fixtures.
CANONICAL_TYPES = frozenset({
    "concept", "decision", "gotcha", "convention", "runbook", "architecture", "howto",
    "reference", "schema", "metric", "api", "dataset", "table", "evaluation", "note",
    "bigquery table",
})

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "ftp://", "tel:", "//")
# A line opening/closing a fenced code block (``` or ~~~). Toggled per-line so log/link
# scanners skip example content inside fences (a date heading or link in a ```markdown
# example is documentation, not a real entry).
FENCE_RE = re.compile(r"^(```|~~~)")

# Frontmatter parse outcomes.
NONE = "none"          # no frontmatter block at all
UNPARSEABLE = "bad"    # opened a block we can't parse (or it never closed)
OK = "ok"


def parse_frontmatter(text):
    """Return (status, dict). Restricted grammar: blank lines, '# comments',
    'key: scalar', and 'key:' followed by indented '  - item' lists. Anything
    else -> UNPARSEABLE (fail closed; we only validate files we authored)."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return (NONE, None)
    close = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close = i
            break
    if close is None:
        return (UNPARSEABLE, None)

    body = lines[1:close]
    data = {}
    i = 0
    while i < len(body):
        line = body[i]
        if line.strip() == "" or line.lstrip().startswith("#"):
            i += 1
            continue
        if "\t" in line:
            return (UNPARSEABLE, None)
        key_indent = len(line) - len(line.lstrip())
        m = KEY_RE.match(line)
        if not m:
            return (UNPARSEABLE, None)
        key, raw = m.group(1), m.group(2).strip()
        # flow collections are outside the restricted grammar
        if raw[:1] in ("{", "["):
            return (UNPARSEABLE, None)
        if raw == "":
            # may be a block list: consume following '- item' lines. A YAML block sequence may
            # sit at the same indent as its key (zero-indent is valid), so accept any item whose
            # dash indent is >= the owning key's indent.
            items = []
            j = i + 1
            while j < len(body):
                lm = LIST_ITEM_RE.match(body[j])
                if not lm or len(lm.group(1)) < key_indent:
                    break
                items.append(_unquote(lm.group(2).strip()))
                j += 1
            data[key] = items if items else ""
            i = j
        else:
            data[key] = _unquote(raw)
            i += 1
    return (OK, data)


def _unquote(v):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def classify(path, bundle_root):
    name = os.path.basename(path)
    if name == "index.md":
        parent = os.path.dirname(os.path.abspath(path))
        return "root_index" if parent == os.path.abspath(bundle_root) else "subdir_index"
    if name == "log.md":
        return "log"
    return "concept"


def _has_flow_collection(text):
    """True if the frontmatter block holds a `key: [...]`/`key: {...}` flow collection — the
    one UNPARSEABLE cause worth a specific message (the restricted grammar wants block lists)."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return False
    for line in lines[1:]:
        if line.rstrip() == "---":
            break
        m = KEY_RE.match(line)
        if m and m.group(2).strip()[:1] in ("[", "{"):
            return True
    return False


def check_concept(text, relpath, findings):
    status, fm = parse_frontmatter(text)
    if status != OK:
        if status == NONE:
            why = "no frontmatter block"
        elif _has_flow_collection(text):
            why = "flow collections `[...]`/`{...}` are not supported — use block-list form"
        else:
            why = "frontmatter is not parseable"
        findings.append(_f("ERROR", "R1", relpath, 1, "Concept must have parseable YAML frontmatter (%s)." % why))
        return
    val = fm.get("type")
    # OKF §3 requires `type` to be a non-empty *string*; a list (any length) is invalid.
    invalid = val is None or (isinstance(val, str) and val.strip() == "") or isinstance(val, list)
    if invalid:
        findings.append(_f("ERROR", "R2", relpath, _key_lookup(text, "type")[0],
                           "Concept frontmatter must contain a non-empty `type` field (a string, not a list)."))
        return
    # R5 (report-only): a valid non-empty type that drifts from the canonical vocabulary. Matched
    # case-insensitively — a case-only variant (`Table` vs `table`) is tolerated silently so the
    # OKF-example fixture corpus stays green; only genuinely off-vocabulary values (e.g. two-word
    # `Architecture Decision`) get the nudge.
    if val.strip().lower() not in CANONICAL_TYPES:
        findings.append(_f("WARNING", "R5", relpath, _key_lookup(text, "type")[0],
                           'type "%s" is not in the canonical vocabulary — prefer one of: %s'
                           % (val.strip(), ", ".join(sorted(CANONICAL_TYPES)))))


def check_root_index(text, relpath, findings):
    status, fm = parse_frontmatter(text)
    if status == NONE:
        return  # frontmatter optional on root index
    if status == UNPARSEABLE:
        findings.append(_f("ERROR", "R3b", relpath, 1, "Root index.md frontmatter is not parseable."))
        return
    extra = sorted(k for k in fm if k != "okf_version")
    if extra:
        findings.append(_f("ERROR", "R3b", relpath, 1,
                           "Root index.md frontmatter may only contain `okf_version`; found: %s." % ", ".join(extra)))
    if "okf_version" in fm:
        # Spec §3/§6 mandate the *quoted* string form `okf_version: "0.1"`. The restricted
        # parser does no YAML type coercion, so check the raw value verbatim (narrow: this one
        # line only — no quote-tracking elsewhere). Both wrong-version and unquoted-0.1 fail here.
        line, raw = _key_lookup(text, "okf_version")
        if raw != '"0.1"':
            findings.append(_f("ERROR", "R3b", relpath, line,
                               'Root index.md `okf_version` must be the quoted string "0.1" (got %s).' % raw))


def check_subdir_index(text, relpath, findings):
    lines = text.split("\n")
    # Only a real frontmatter block counts: a leading `---` with a matching closing `---`.
    # A body that merely opens with a `---` thematic break (no closing) is not frontmatter.
    if lines and lines[0].rstrip() == "---" and any(l.rstrip() == "---" for l in lines[1:]):
        findings.append(_f("ERROR", "R3a", relpath, 1,
                           "Subdirectory index.md must have zero frontmatter."))


def check_log(text, relpath, findings):
    lines = text.split("\n")
    valid_dates = []  # (lineno, date) in document order, for headings that parse
    h2_count = 0
    in_fence = False
    for n, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # date headings / bullets inside a ``` example are not real log entries
        m = ATX_HEADING_RE.match(line)
        if m and len(m.group(1)) != 2 and DATE_CANDIDATE_RE.match(m.group(2).strip()):
            # A date heading at the wrong ATX level (H1/H3/…) — would skip the H2 checks.
            findings.append(_f("ERROR", "R3c", relpath, n,
                               "log.md date heading %r must be an H2 (`## YYYY-MM-DD`)." % m.group(2).strip()))
            continue
        if line.startswith("## "):
            h2_count += 1
            heading = line[3:].strip()
            if not DATE_RE.match(heading):
                findings.append(_f("ERROR", "R3c", relpath, n,
                                   "log.md date heading must be ISO YYYY-MM-DD (got %r)." % heading))
                continue
            try:
                d = date.fromisoformat(heading)
            except ValueError:
                findings.append(_f("ERROR", "R3c", relpath, n,
                                   "log.md date heading is not a real date (%r)." % heading))
                continue
            valid_dates.append((n, d))
        elif line.startswith("* ") or line.startswith("- "):
            bullet = line[2:].lstrip()
            if not bullet.startswith(LOG_PREFIXES):
                findings.append(_f("ERROR", "R3c", relpath, n,
                                   "log.md entry must begin with one of **Update**/**Creation**/**Initialization**."))
    # newest-first: dates non-increasing in document order
    for (n1, d1), (n2, d2) in zip(valid_dates, valid_dates[1:]):
        if d2 > d1:
            findings.append(_f("ERROR", "R3c", relpath, n2,
                               "log.md headings must be newest-first; %s appears after %s." % (d2, d1)))
            break
    if h2_count == 0:
        findings.append(_f("ERROR", "R3c", relpath, 1,
                           "log.md has no `## YYYY-MM-DD` date section."))


def check_links(text, abspath, bundle_root, relpath, findings):
    """R4 (report-only): flag internal markdown links whose target doesn't resolve.
    Resolves `/...` from the bundle root and everything else relative to the file's
    directory; skips external schemes and bare `#anchor` links. Per spec §5 broken
    links are *tolerated*, so these are WARNINGs that never affect the exit code."""
    base = os.path.dirname(abspath)
    in_fence = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # links inside a ``` example are documentation, not real cross-links
        for m in LINK_RE.finditer(line):
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
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue  # was a pure fragment
            if target.startswith("/"):
                resolved = os.path.join(bundle_root, target.lstrip("/"))
            else:
                resolved = os.path.join(base, target)
            resolved = os.path.normpath(resolved)
            exists = os.path.isdir(resolved) if target.endswith("/") else os.path.isfile(resolved)
            if not exists:
                findings.append(_f("WARNING", "R4", relpath, n,
                                   "Link target does not resolve: %s" % target))


def _key_lookup(text, key):
    """Return (lineno, raw_value) for `key`'s first frontmatter line — (1, '') if absent.
    `raw_value` is verbatim (not unquoted)."""
    for n, line in enumerate(text.split("\n"), 1):
        m = KEY_RE.match(line)
        if m and m.group(1) == key:
            return n, m.group(2).strip()
    return 1, ""


def _f(severity, rule, file, line, message):
    return {"severity": severity, "rule": rule, "file": file, "line": line, "message": message}


def collect_targets(target):
    """Return (bundle_root, [abs md paths]) or raise ValueError for operational errors."""
    if os.path.isdir(target):
        md = []
        for root, _dirs, files in os.walk(target):
            for fn in files:
                if fn.endswith(".md"):
                    md.append(os.path.join(root, fn))
        return (target, sorted(md))
    if os.path.isfile(target):
        if os.path.basename(target) == "index.md":
            raise ValueError("cannot validate a bare index.md (root vs subdir is undecidable); pass the bundle directory")
        return (os.path.dirname(os.path.abspath(target)) or ".", [target])
    raise ValueError("no such file or directory: %s" % target)


def validate(target):
    bundle_root, paths = collect_targets(target)
    findings = []
    for p in paths:
        rel = os.path.relpath(p, bundle_root).replace(os.sep, "/")
        try:
            with open(p, "r", encoding="utf-8") as fh:
                text = fh.read()
            if text.startswith("﻿"):
                text = text[1:]  # strip a leading UTF-8 BOM so leading-`---` checks see line 1
        except OSError as e:
            raise ValueError("cannot read %s: %s" % (rel, e))
        except UnicodeDecodeError:
            # One bad file must not abort the whole bundle: flag it and keep validating the rest.
            findings.append(_f("ERROR", "R1", rel, 1, "File is not valid UTF-8."))
            continue
        kind = classify(p, bundle_root)
        if kind == "concept":
            check_concept(text, rel, findings)
        elif kind == "root_index":
            check_root_index(text, rel, findings)
        elif kind == "subdir_index":
            check_subdir_index(text, rel, findings)
        elif kind == "log":
            check_log(text, rel, findings)
        check_links(text, p, bundle_root, rel, findings)
    findings.sort(key=lambda f: (f["file"], f["line"], f["rule"]))
    return bundle_root, len(paths), findings


def main(argv):
    mode, fmt, target = "strict", "text", None
    it = iter(argv)
    for a in it:
        if a == "--mode":
            mode = next(it, "")
        elif a == "--format":
            fmt = next(it, "")
        elif a.startswith("--"):
            sys.stderr.write("unknown flag: %s\n" % a)
            return 2
        elif target is None:
            target = a
        else:
            sys.stderr.write("unexpected extra argument: %s\n" % a)
            return 2

    if target is None:
        sys.stderr.write("usage: doctor.py <bundle-or-file> [--mode strict|lenient] [--format text|json]\n")
        return 2
    if mode not in ("strict", "lenient"):
        sys.stderr.write("invalid --mode: %s\n" % mode)
        return 2
    if fmt not in ("text", "json"):
        sys.stderr.write("invalid --format: %s\n" % fmt)
        return 2
    if mode == "lenient":
        sys.stderr.write("lenient consumer mode is not implemented in Phase 1 (deferred to Phase 4)\n")
        return 2

    try:
        _root, files_checked, findings = validate(target)
    except ValueError as e:
        sys.stderr.write("error: %s\n" % e)
        return 2

    errors = sum(1 for f in findings if f["severity"] == "ERROR")
    warnings = sum(1 for f in findings if f["severity"] == "WARNING")
    ok = errors == 0

    if fmt == "json":
        obj = {
            "schema": SCHEMA,
            "mode": mode,
            "target": target,
            "ok": ok,
            "summary": {"errors": errors, "warnings": warnings, "files_checked": files_checked},
            "findings": findings,
        }
        print(json.dumps(obj, sort_keys=True, indent=2))
    else:
        for f in findings:
            label = "WARN" if f["severity"] == "WARNING" else "ERROR"
            print("%-5s %-4s %s:%d   %s" % (label, f["rule"], f["file"], f["line"], f["message"]))
        print("Result: %s — %d errors, %d warnings" % ("PASS" if ok else "FAIL", errors, warnings))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
