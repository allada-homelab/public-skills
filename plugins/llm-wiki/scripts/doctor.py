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

Rules (see PHASE_1_TECH_PLAN.md §5):
    R1   concept has parseable YAML frontmatter
    R2   concept frontmatter has a non-empty `type`
    R3a  subdirectory index.md has zero frontmatter
    R3b  root index.md frontmatter keys ⊆ {okf_version}, and okf_version == "0.1"
    R3c  log.md: ISO YYYY-MM-DD headings, newest-first, bold **Update/Creation/Initialization** bullets
"""
import json
import os
import re
import sys
from datetime import date

SCHEMA = "okf-doctor/1"
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
LIST_ITEM_RE = re.compile(r"^\s+-\s+(.*)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOG_PREFIXES = ("**Update**", "**Creation**", "**Initialization**")

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
        m = KEY_RE.match(line)
        if not m:
            return (UNPARSEABLE, None)
        key, raw = m.group(1), m.group(2).strip()
        # flow collections are outside the restricted grammar
        if raw[:1] in ("{", "["):
            return (UNPARSEABLE, None)
        if raw == "":
            # may be a block list: consume following indented '- item' lines
            items = []
            j = i + 1
            while j < len(body) and LIST_ITEM_RE.match(body[j]):
                items.append(_unquote(LIST_ITEM_RE.match(body[j]).group(1).strip()))
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


def check_concept(text, relpath, findings):
    status, fm = parse_frontmatter(text)
    if status != OK:
        why = "no frontmatter block" if status == NONE else "frontmatter is not parseable"
        findings.append(_f("ERROR", "R1", relpath, 1, "Concept must have parseable YAML frontmatter (%s)." % why))
        return
    val = fm.get("type")
    empty = val is None or (isinstance(val, str) and val.strip() == "") or (isinstance(val, list) and not val)
    if empty:
        findings.append(_f("ERROR", "R2", relpath, _key_line(text, "type"),
                           "Concept frontmatter must contain a non-empty `type` field."))


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
    if "okf_version" in fm and fm["okf_version"] != "0.1":
        findings.append(_f("ERROR", "R3b", relpath, _key_line(text, "okf_version"),
                           'Root index.md `okf_version` must be "0.1" (got "%s").' % fm["okf_version"]))


def check_subdir_index(text, relpath, findings):
    if text.split("\n")[0].rstrip() == "---":
        findings.append(_f("ERROR", "R3a", relpath, 1,
                           "Subdirectory index.md must have zero frontmatter."))


def check_log(text, relpath, findings):
    lines = text.split("\n")
    valid_dates = []  # (lineno, date) in document order, for headings that parse
    for n, line in enumerate(lines, 1):
        if line.startswith("## "):
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
        elif line.startswith("* "):
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


def _key_line(text, key):
    for n, line in enumerate(text.split("\n"), 1):
        m = KEY_RE.match(line)
        if m and m.group(1) == key:
            return n
    return 1


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
        except OSError as e:
            raise ValueError("cannot read %s: %s" % (rel, e))
        kind = classify(p, bundle_root)
        if kind == "concept":
            check_concept(text, rel, findings)
        elif kind == "root_index":
            check_root_index(text, rel, findings)
        elif kind == "subdir_index":
            check_subdir_index(text, rel, findings)
        elif kind == "log":
            check_log(text, rel, findings)
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
