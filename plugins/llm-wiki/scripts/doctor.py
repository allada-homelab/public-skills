#!/usr/bin/env python3
"""OKF v0.2 conformance validator ("Doctor") for the /llm-wiki plugin.

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
    R3b  root index.md frontmatter keys ⊆ {okf_version}, and okf_version == "0.2"
    R3c  log.md: ISO YYYY-MM-DD headings, newest-first, bold **Update/Creation/Initialization** bullets
    R4   internal markdown links resolve (WARNING only — broken links are tolerated per OKF spec §5)
    R5   concept `type` is in the canonical vocabulary (WARNING only — OKF §3 only requires a
         non-empty type; R5 is a curation nudge to keep grouping/analytics stable, never an ERROR)
    R6   Wiki-managed claim/evidence provenance is complete, stable, and objectively grounded
    R7   bundle shape (directory targets only; WARNING, never blocks): zero concept files, or
         concepts present without a root index.md — both are the signature of a moved/emptied
         bundle, which would otherwise validate byte-identically to a healthy one
    R8   OKF v0.2 trust/lifecycle/provenance families (§5) are well-shaped *when present* —
         `generated`, `verified`, `status`, `stale_after`, `sources`, `usage_window`, and the §7
         actor convention. A missing family is never a finding (§11 forbids rejecting for one);
         footnote→`sources[].id` attribution is report-only
    R9   legacy v0.1 fields superseded by v0.2 (§13.1): `timestamp`, a bare scalar `verified:`,
         a body `Citations` section, and `okf_version: "0.1"` (WARNING — `bundle_ops apply`
         rewrites them to v0.2 shape in place, so installed bundles keep validating)
"""
import json
import os
import re
import sys
from datetime import date, datetime

from provenance import ProvenanceError, extract as extract_provenance, validation_errors as provenance_errors

SCHEMA = "okf-doctor/1"
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
FLOW_KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The OKF revision this plugin produces, and the older revisions it still reads. A legacy
# bundle is warned about (R9) and rewritten to current shape by `bundle_ops apply`, never
# rejected — spec §13.1 lets a v0.2 consumer fall back to the v0.1 fields.
OKF_VERSION = "0.2"
LEGACY_OKF_VERSIONS = frozenset({"0.1"})

# §7 actor convention: `<producer>/<version>` for tools, `human:<id>`, `process:<id>`.
ACTOR_RE = re.compile(r"^(?:human:\S+|process:\S+|[A-Za-z0-9_.-]+/\S+)$")
STATUS_VALUES = frozenset({"draft", "stable", "deprecated"})
# §5.1 per-source credibility signals, and the sibling that frames every usage_count.
SOURCE_DATE_FIELDS = ("last_modified",)
FOOTNOTE_REF_RE = re.compile(r"(?<!\\)\[\^([^\]]+)\]")
CITATIONS_HEADING_RE = re.compile(r"^#{1,6}\s+Citations\s*$")
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


class _YamlError(Exception):
    """Frontmatter outside the supported grammar — reported as R1."""


def parse_frontmatter(text):
    """Return (status, dict). Supported grammar: scalars, block lists, block mappings, and
    flow collections (`{a: b}` / `[a, b]`) nested to any depth — enough for the OKF v0.2
    trust/provenance families (§5) without a YAML dependency. Anything else -> UNPARSEABLE
    (fail closed; we only validate files we authored)."""
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
    try:
        items = _significant(lines[1:close])
        data, consumed = _parse_map(items, 0, items[0][0] if items else 0)
        if consumed != len(items):
            raise _YamlError("unconsumed frontmatter lines")
    except _YamlError:
        return (UNPARSEABLE, None)
    return (OK, data)


def _significant(body):
    """[(indent, text)] with blank lines and whole-line comments dropped."""
    out = []
    for raw in body:
        if "\t" in raw:
            raise _YamlError("tab indentation")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip()), stripped))
    return out


def _parse_map(items, i, indent):
    """Parse a block mapping whose keys sit at `indent`. Returns (dict, next index)."""
    data = {}
    while i < len(items):
        ind, line = items[i]
        if ind < indent:
            break
        if ind > indent or line.startswith("- ") or line == "-":
            raise _YamlError("expected a mapping key")
        m = KEY_RE.match(line)
        if not m:
            raise _YamlError("not a mapping key: %s" % line)
        key, raw = m.group(1), _strip_inline_comment(m.group(2).strip())
        if raw:
            data[key] = _scalar_or_flow(raw)
            i += 1
            continue
        # `key:` with nothing after it — a nested block, or an empty value.
        data[key], i = _parse_nested(items, i + 1, ind)
    return data, i


def _parse_nested(items, i, parent_indent):
    """Parse the block that follows a bare `key:`. Returns (value, next index)."""
    if i >= len(items):
        return "", i
    ind, line = items[i]
    if line.startswith("- ") or line == "-":
        # A YAML block sequence may sit at its parent key's own indent, so accept ind >= parent.
        if ind < parent_indent:
            return "", i
        return _parse_seq(items, i, ind)
    if ind > parent_indent:
        return _parse_map(items, i, ind)
    return "", i


def _parse_seq(items, i, indent):
    """Parse a block sequence whose `-` markers sit at `indent`. Returns (list, next index)."""
    out = []
    while i < len(items):
        ind, line = items[i]
        if ind != indent or not (line.startswith("- ") or line == "-"):
            break
        rest = _strip_inline_comment(line[1:].strip())
        i += 1
        if not rest:
            value, i = _parse_nested(items, i, indent)
            out.append(value)
            continue
        if rest[0] in "{[":
            out.append(_parse_flow(rest))
            continue
        m = KEY_RE.match(rest)
        if not m:
            out.append(_unquote(rest))
            continue
        # `- key: value` opens a mapping item; its remaining keys are indented past the dash.
        key, raw = m.group(1), m.group(2).strip()
        item = {}
        if raw:
            item[key] = _scalar_or_flow(raw)
        else:
            item[key], i = _parse_nested(items, i, ind)
        if i < len(items) and items[i][0] > ind and not items[i][1].startswith("- "):
            rest_keys, i = _parse_map(items, i, items[i][0])
            item.update(rest_keys)
        out.append(item)
    return out, i


def _strip_inline_comment(raw):
    """Drop a trailing ` # comment` sitting outside quotes and flow collections."""
    depth, quote = 0, None
    for n, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == "#" and depth == 0 and n > 0 and raw[n - 1] in " \t":
            return raw[:n].rstrip()
    return raw


def _scalar_or_flow(raw):
    return _parse_flow(raw) if raw[0] in "{[" else _unquote(raw)


def _parse_flow(raw):
    value, rest = _flow_value(raw)
    if rest.strip():
        raise _YamlError("trailing content after flow collection")
    return value


def _flow_value(s):
    """Parse one flow-collection value. Returns (value, unconsumed remainder)."""
    s = s.lstrip()
    if not s:
        raise _YamlError("empty flow value")
    if s[0] == "{":
        return _flow_items(s[1:], "}", {})
    if s[0] == "[":
        return _flow_items(s[1:], "]", [])
    if s[0] in "'\"":
        quote, buf, n = s[0], [], 1
        while n < len(s):
            if s[n] == quote:
                return "".join(buf), s[n + 1:]
            buf.append(s[n])
            n += 1
        raise _YamlError("unterminated quote")
    n = 0
    while n < len(s) and s[n] not in ",}]":
        n += 1
    return s[:n].strip(), s[n:]


def _flow_items(s, closer, into):
    """Parse flow entries up to `closer` into a dict or list. Returns (collection, remainder)."""
    s = s.lstrip()
    if s[:1] == closer:
        return into, s[1:]
    while True:
        if isinstance(into, dict):
            m = FLOW_KEY_RE.match(s)
            if not m:
                raise _YamlError("expected `key:` in flow mapping")
            key = m.group(1)
            into[key], s = _flow_value(s[m.end():])
        else:
            value, s = _flow_value(s)
            into.append(value)
        s = s.lstrip()
        if s[:1] == ",":
            s = s[1:].lstrip()
            continue
        if s[:1] == closer:
            return into, s[1:]
        raise _YamlError("expected `,` or `%s` in flow collection" % closer)


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
    check_v02_families(fm, text, relpath, findings)
    check_legacy_fields(fm, text, relpath, findings)
    managed = str(fm.get("wiki_managed", "")).lower() == "true"
    try:
        provenance = extract_provenance(text)
    except ProvenanceError as exc:
        findings.append(_f("ERROR", "R6", relpath, 1, str(exc)))
        return
    if managed and provenance is None:
        findings.append(_f("ERROR", "R6", relpath, 1,
                           "Wiki-managed concept must contain a `## Wiki provenance` JSON block."))
    elif provenance is not None:
        line = next(
            (n for n, value in enumerate(text.split("\n"), 1)
             if value.strip() == "## Wiki provenance"),
            1,
        )
        for message in provenance_errors(provenance):
            findings.append(_f("ERROR", "R6", relpath, line, message))


def _iso_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _plain_date(value):
    return isinstance(value, str) and bool(DATE_RE.match(value.strip()))


def _body(text):
    """(body, offset) — everything after a closing frontmatter `---`, plus the number of lines
    consumed before it, so body findings can be reported at file-relative line numbers like
    every other rule."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return text, 0
    for n in range(1, len(lines)):
        if lines[n].rstrip() == "---":
            return "\n".join(lines[n + 1:]), n + 1
    return "", 0


def _unfenced(body_and_offset):
    """[(file lineno, line)] for body lines outside fenced code blocks."""
    body, offset = body_and_offset
    out, in_fence = [], False
    for n, line in enumerate(body.split("\n"), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((n + offset, line))
    return out


def _actor_errors(value, label, relpath, line, findings):
    """§7: an identity field must be a non-empty string in the actor convention."""
    if not isinstance(value, str) or not value.strip():
        findings.append(_f("ERROR", "R8", relpath, line,
                           "`%s` is required and must be a non-empty actor string (§7)." % label))
    elif not ACTOR_RE.match(value.strip()):
        findings.append(_f("ERROR", "R8", relpath, line,
                           '`%s` must follow the §7 actor convention — `<producer>/<version>`, '
                           '`human:<id>`, or `process:<id>` (got "%s").' % (label, value.strip())))


def check_v02_families(fm, text, relpath, findings):
    """R8: an OKF v0.2 trust/lifecycle/provenance family that is PRESENT must be well-shaped.
    Absence is never a finding — §11 forbids rejecting a concept for a missing optional family."""
    generated = fm.get("generated")
    if generated is not None:
        line = _key_lookup(text, "generated")[0]
        if not isinstance(generated, dict):
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`generated` must be a mapping with `by` and `at` (§5.2)."))
        else:
            _actor_errors(generated.get("by"), "generated.by", relpath, line, findings)
            if "at" in generated and not _iso_datetime(generated.get("at")):
                findings.append(_f("ERROR", "R8", relpath, line,
                                   "`generated.at` must be an ISO 8601 datetime (§5.2)."))

    verified = fm.get("verified")
    # A bare scalar is the legacy v0.1 shape — R9 owns it, so don't double-report here.
    if verified is not None and not isinstance(verified, str):
        line = _key_lookup(text, "verified")[0]
        # §5.2/§11: a bare mapping MUST be treated as a one-element list.
        entries = [verified] if isinstance(verified, dict) else verified
        if not isinstance(entries, list) or not entries:
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`verified` must be a `{ by, at }` mapping or a non-empty list of them (§5.2)."))
        else:
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    findings.append(_f("ERROR", "R8", relpath, line,
                                       "`verified[%d]` must be a `{ by, at }` mapping (§5.2)." % index))
                    continue
                _actor_errors(entry.get("by"), "verified[%d].by" % index, relpath, line, findings)
                if not _iso_datetime(entry.get("at")):
                    findings.append(_f("ERROR", "R8", relpath, line,
                                       "`verified[%d].at` must be an ISO 8601 datetime (§5.2)." % index))

    status = fm.get("status")
    if status is not None:
        if not isinstance(status, str) or status.strip() not in STATUS_VALUES:
            findings.append(_f("ERROR", "R8", relpath, _key_lookup(text, "status")[0],
                               "`status` must be one of %s (§5.4)." % ", ".join(sorted(STATUS_VALUES))))

    if "stale_after" in fm and not _plain_date(fm.get("stale_after")):
        findings.append(_f("ERROR", "R8", relpath, _key_lookup(text, "stale_after")[0],
                           "`stale_after` must be an absolute date `YYYY-MM-DD` (§5.5)."))

    source_ids = check_sources(fm, text, relpath, findings)

    window = fm.get("usage_window")
    if window is not None:
        line = _key_lookup(text, "usage_window")[0]
        if not isinstance(window, dict):
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`usage_window` must be a `{ from, to }` mapping (§5.1)."))
        else:
            for bound in ("from", "to"):
                if bound in window and not _plain_date(window.get(bound)):
                    findings.append(_f("ERROR", "R8", relpath, line,
                                       "`usage_window.%s` must be a date `YYYY-MM-DD` (§5.1)." % bound))

    check_footnote_attribution(fm, text, source_ids, relpath, findings)


def check_sources(fm, text, relpath, findings):
    """R8 for §5.1 `sources`. Returns the set of declared source ids (for footnote joining)."""
    sources = fm.get("sources")
    if sources is None:
        return set()
    line = _key_lookup(text, "sources")[0]
    if not isinstance(sources, list) or not sources:
        findings.append(_f("ERROR", "R8", relpath, line,
                           "`sources` must be a non-empty list of entries (§5.1)."))
        return set()
    ids, seen = set(), set()
    for index, entry in enumerate(sources):
        if not isinstance(entry, dict):
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`sources[%d]` must be a mapping (§5.1)." % index))
            continue
        resource = entry.get("resource")
        if not isinstance(resource, str) or not resource.strip():
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`sources[%d].resource` is required within an entry (§5.1)." % index))
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and entry_id.strip():
            key = entry_id.strip()
            # ids are the join key for per-claim footnote attribution — duplicates misattribute.
            if key in seen:
                findings.append(_f("ERROR", "R8", relpath, line,
                                   '`sources` id "%s" is used more than once (§5.1).' % key))
            seen.add(key)
            ids.add(key)
        for field in SOURCE_DATE_FIELDS:
            if field in entry and not _plain_date(entry.get(field)):
                findings.append(_f("ERROR", "R8", relpath, line,
                                   "`sources[%d].%s` must be a date `YYYY-MM-DD` (§5.1)." % (index, field)))
        count = entry.get("usage_count")
        if count is not None and not (isinstance(count, str) and count.strip().isdigit()):
            findings.append(_f("ERROR", "R8", relpath, line,
                               "`sources[%d].usage_count` must be an integer (§5.1)." % index))
    return ids


def check_footnote_attribution(fm, text, source_ids, relpath, findings):
    """R8 (report-only): a `[^label]` footnote joins into `sources[].id` (§5.1). Only checked
    once a concept declares `sources` — a bundle not using the convention is not doing it wrong."""
    if fm.get("sources") is None:
        return
    body = _body(text)
    for lineno, line in _unfenced(body):
        for match in FOOTNOTE_REF_RE.finditer(line):
            label = match.group(1).strip()
            if label and label not in source_ids:
                findings.append(_f("WARNING", "R8", relpath, lineno,
                                   'footnote [^%s] does not match any `sources[].id` — per-claim '
                                   'attribution resolves through that join key (§5.1).' % label))


def check_legacy_fields(fm, text, relpath, findings):
    """R9 (report-only): v0.1 fields superseded by v0.2 (§13.1). Warnings, never errors — the
    spec permits consuming them, and `bundle_ops apply` rewrites them to v0.2 shape in place."""
    if "timestamp" in fm:
        findings.append(_f("WARNING", "R9", relpath, _key_lookup(text, "timestamp")[0],
                           "`timestamp` is superseded by `generated: { by, at }` (§13.1) — "
                           "it will be migrated on the next write."))
    if isinstance(fm.get("verified"), str):
        findings.append(_f("WARNING", "R9", relpath, _key_lookup(text, "verified")[0],
                           "a bare `verified:` datetime is superseded by a `{ by, at }` entry "
                           "(§5.2) — it will be migrated on the next write."))
    for lineno, line in _unfenced(_body(text)):
        if CITATIONS_HEADING_RE.match(line):
            findings.append(_f("WARNING", "R9", relpath, lineno,
                               "a body `Citations` section is superseded by the `sources` "
                               "frontmatter family (§13.1)."))
            break


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
        # Spec §8/§12 mandate the *quoted* string form `okf_version: "0.2"`. The parser does no
        # YAML type coercion, so check the raw value verbatim (narrow: this one line only — no
        # quote-tracking elsewhere), which also catches the unquoted `0.2` float form.
        line, raw = _key_lookup(text, "okf_version")
        if raw in ('"%s"' % v for v in LEGACY_OKF_VERSIONS):
            findings.append(_f("WARNING", "R9", relpath, line,
                               'Root index.md declares OKF %s; this producer writes "%s" — it will '
                               "be migrated on the next write." % (raw, OKF_VERSION)))
        elif raw != '"%s"' % OKF_VERSION:
            findings.append(_f("ERROR", "R3b", relpath, line,
                               'Root index.md `okf_version` must be the quoted string "%s" (got %s).'
                               % (OKF_VERSION, raw)))


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


def check_bundle_shape(paths, bundle_root, findings):
    """R7 (report-only, directory targets only): a healthy bundle and one whose contents were
    moved or emptied must not validate identically. Warnings, never errors — an auto-inited
    bundle is legitimately empty until its first capture lands."""
    kinds = [classify(p, bundle_root) for p in paths]
    concepts = kinds.count("concept")
    if concepts == 0:
        findings.append(_f("WARNING", "R7", ".", 1,
                           "Bundle contains no concept files — if this project should have a wiki, "
                           "the bundle may have been moved or emptied."))
    elif "root_index" not in kinds:
        findings.append(_f("WARNING", "R7", ".", 1,
                           "Bundle has %d concept(s) but no root index.md — regenerate it "
                           "(bundle_ops.py index)." % concepts))


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
    if os.path.isdir(target):
        check_bundle_shape(paths, bundle_root, findings)
    findings.sort(key=lambda f: (f["file"], f["line"], f["rule"]))
    return bundle_root, len(paths), findings


USAGE = "usage: doctor.py <bundle-or-file> [--mode strict|lenient] [--format text|json]\n"


def main(argv):
    mode, fmt, target = "strict", "text", None
    it = iter(argv)
    for a in it:
        if a in ("-h", "--help"):
            sys.stdout.write(USAGE)
            return 0
        elif a == "--mode":
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
        sys.stderr.write(USAGE)
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
