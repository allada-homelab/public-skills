#!/usr/bin/env python3
"""Report-only secret scanner for the /llm-wiki plugin (Phase 1).

Scans one pending payload (a file path, or '-' for stdin) for credential-shaped
content and reports findings. **Always exits 0 in Phase 1** — the calling command
surfaces findings in the confirm-first diff; the human decides. Phase 3 re-wires the
caller (a PreToolUse hook) to treat findings as blocking; this script is unchanged.

Usage:
    secret_scan.py <file-or-"-"> [--format text|json]

Two stages:
    1. Labeled high-precision regexes (cloud keys, API tokens, PEM blocks, conn strings).
    2. Entropy gate for unmatched long tokens (Shannon >= 4.0 bits/char, >= 2 charset classes).

Documentation suppression (a knowledge base legitimately contains example credentials):
    - A line carrying the `pragma: allowlist secret` inline marker (the detect-secrets
      convention) is skipped entirely — the explicit, per-line opt-out, and the escape hatch
      for format-valid example keys (`AKIA…EXAMPLE`) and illustrative ciphertext.
    - A finding whose matched value is an obvious human placeholder (`CHANGEME`,
      `REPLACE_WITH_…`, `<your-password-here>`, `…_HERE`, `XXXX`, `TODO`/`FIXME`) is dropped.
      Format-valid example keys are NOT placeholder-suppressed — use the pragma for those.

Previews are redacted (first 4 chars + ellipsis) — the full secret is never emitted.
"""
import json
import math
import re
import sys

SCHEMA = "okf-secret-scan/1"
ENTROPY_MIN = 4.0          # bits/char — the one tunable knob (retuned in Phase 3)
ENTROPY_MIN_LEN = 20

# (category, regex, high_confidence). A high-confidence labeled key (format-specific cloud/API
# token, PEM block) is a near-certain leak: it is NEVER placeholder-suppressed, only the per-line
# `pragma: allowlist secret` opt-out can silence it. Low-confidence patterns are generic
# `key=value` shapes that legitimately match documentation placeholders (CHANGEME, <your-…>),
# so those stay placeholder-suppressed.
PATTERNS = [
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), True),
    ("gcp_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), True),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), True),
    ("github_token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b"), True),
    ("openai_key", re.compile(r"\bsk-(?:ant-)?[0-9A-Za-z_\-]{20,}\b"), True),
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), True),
    ("bearer_token", re.compile(r"(?i)\bauthorization:\s*bearer\s+([0-9A-Za-z._\-]{16,})"), False),
    ("connection_string_creds", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s:/@]+)@"), False),
    ("jdbc_password", re.compile(r"(?i)\bpassword=([^\s;&]+)"), False),
    ("assigned_secret", re.compile(
        r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*[\"']?([^\s\"']{8,})"), False),
]

# Entropy candidates are *contiguous opaque runs* — deliberately excludes `/`, `-`, and `.`
# (and `#`, never in the class) so the gate does NOT span path/URL separators or hyphen-delimited
# slugs. A real unlabeled secret is one unbroken alnum(+`=`/`_`/`+`) run; a markdown link target
# (`planning/PRODUCT_PLAN.md`), a URL (`github.com/org/repo/blob/main`), or a slug
# (`future-ideas--backlog-not-committed`) is short word-pieces joined by separators, so each piece
# falls under the length floor and never reaches the entropy check. Base64/url-safe secrets keep
# `+`, `=`, `_`; only `-`/`/`-split base64 loses a contiguous run (acceptable on a backstop gate —
# labeled Stage-1 patterns catch the named high-value keys).
TOKEN_RE = re.compile(r"[A-Za-z0-9+=_]{%d,}" % ENTROPY_MIN_LEN)

# Inline "this is not a real secret" marker (detect-secrets convention) — skips the whole line.
PRAGMA_RE = re.compile(r"(?i)pragma:\s*allowlist\s+secret")

# Obvious human placeholders — a matched value containing one of these is documentation, not a
# leak. Deliberately does NOT include bare "EXAMPLE": format-valid example keys (AKIA…EXAMPLE) stay
# detected, and the pragma is their opt-out.
# NB: no `x{4,}` rule — it vetoed real keys that merely contain `xxxx`/`XXXX`
# (e.g. `ghp_…xxxx…`, `wJalrXXXX…`), silently dropping leaks. Placeholder suppression is
# anchored on explicit human-placeholder words, never on a run of `x`.
PLACEHOLDER_RE = re.compile(
    r"(?i)(?:change[_-]?me|replace[_-]?with|replace[_-]?me|placeholder|redacted|dummy|"
    r"your[_-]|[_-]here\b|<[^>]+>|\btodo\b|\bfixme\b)")


def shannon_entropy(s):
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def charset_classes(s):
    classes = 0
    if re.search(r"[a-z]", s):
        classes += 1
    if re.search(r"[A-Z]", s):
        classes += 1
    if re.search(r"[0-9]", s):
        classes += 1
    if re.search(r"[^A-Za-z0-9]", s):
        classes += 1
    return classes


def redact(value):
    value = value.strip().strip("\"'")
    return (value[:4] + "…") if len(value) > 4 else "…"


def scan(text):
    findings = []
    seen = set()  # (line, value) to avoid double-reporting across stages
    for lineno, line in enumerate(text.split("\n"), 1):
        if PRAGMA_RE.search(line):
            continue  # explicitly marked "not a real secret" — skip the whole line
        # Stage 1: labeled patterns.
        for category, rx, high_confidence in PATTERNS:
            for m in rx.finditer(line):
                value = m.group(m.lastindex) if m.lastindex else m.group(0)
                key = (lineno, value)
                if key in seen:
                    continue
                seen.add(key)
                # High-confidence labeled keys are never placeholder-suppressed (only the
                # per-line pragma can silence them); generic low-confidence shapes are.
                if not high_confidence and PLACEHOLDER_RE.search(value):
                    continue  # an obvious placeholder, not a leaked credential
                findings.append({"category": category, "detector": "pattern",
                                 "line": lineno, "preview": redact(value)})
        # Stage 2: entropy gate on unmatched long tokens.
        for m in TOKEN_RE.finditer(line):
            token = m.group(0)
            if (lineno, token) in seen:
                continue
            if PLACEHOLDER_RE.search(token):
                continue
            if shannon_entropy(token) >= ENTROPY_MIN and charset_classes(token) >= 2:
                seen.add((lineno, token))
                findings.append({"category": "high_entropy_token", "detector": "entropy",
                                 "line": lineno, "preview": redact(token)})
    findings.sort(key=lambda f: (f["line"], f["category"], f["preview"]))
    return findings


def main(argv):
    fmt, target = "text", None
    it = iter(argv)
    for a in it:
        if a == "--format":
            fmt = next(it, "")
        elif a.startswith("--"):
            sys.stderr.write("unknown flag: %s\n" % a)
            return 0  # report-only: never fail the caller
        elif target is None:
            target = a
        else:
            sys.stderr.write("unexpected extra argument: %s\n" % a)
            return 0

    if target is None or fmt not in ("text", "json"):
        sys.stderr.write("usage: secret_scan.py <file-or-\"-\"> [--format text|json]\n")
        return 0

    try:
        text = sys.stdin.read() if target == "-" else open(target, "r", encoding="utf-8").read()
    except OSError as e:
        sys.stderr.write("cannot read %s: %s\n" % (target, e))
        return 0

    findings = scan(text)
    if fmt == "json":
        print(json.dumps({"schema": SCHEMA, "target": target,
                          "summary": {"findings": len(findings)}, "findings": findings},
                         sort_keys=True, indent=2))
    else:
        for f in findings:
            print("SECRET %-22s %s:%d   preview=%s" % (f["category"], target, f["line"], f["preview"]))
        print("Potential secrets: %d (report-only)" % len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
