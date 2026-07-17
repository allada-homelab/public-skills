#!/usr/bin/env python3
"""Secret scanner for the /llm-wiki plugin.

Scans one pending payload (a file path, or '-' for stdin) for credential-shaped
content and reports findings. **Always exits 0 by design** — callers key off the
`summary.findings` count in the JSON output, never the exit code. It is the scanner
behind both the *blocking* PreToolUse write guard (`hook_pre_write.py`) and the hard-abort gate
inside `bundle_ops apply` (a hit there halts the write before anything lands).

Usage:
    secret_scan.py <file-or-"-"> [--format text|json]

Two stages:
    1. Labeled high-precision regexes (cloud keys, API tokens, PEM blocks, conn strings).
    2. Entropy gate for unmatched long tokens (Shannon >= 4.0 bits/char, >= 2 charset classes).

Documentation suppression (a knowledge base legitimately contains example credentials):
    - A line carrying the `pragma: allowlist secret` inline marker (the detect-secrets
      convention) suppresses Stage-2 entropy hits and low-confidence generic key=value shapes on
      that line — but NOT the Stage-1 named high-confidence key formats (AWS/GCP/Slack/GitHub/
      OpenAI keys, PEM blocks), which are always redacted regardless of the pragma. The pragma is
      agent-authored content, so it is a smuggling channel: a named-format credential must not be
      silenceable by a pragma the same write introduces. Even a format-valid example key
      (`AKIA…EXAMPLE`) is reported — redact it or write it outside the bundle.
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
ENTROPY_MIN = 4.0          # bits/char — the one tunable knob
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

# Letters-only strict camelCase (lowercase head, capitalized humps, optional trailing acronym) is
# an identifier, not a secret: Kubernetes/API field names (`maxNoOfPodsToEvictPerNode`,
# `guaranteedInstanceManagerCPU`) clear the entropy bar purely on case alternation, and they are
# exactly the vocabulary a wiki must quote verbatim. A >=20-char random token is letters-only only
# ~3% of the time and camelCase-*shaped* essentially never, so this exemption barely dents the
# backstop. Any digit or symbol disqualifies — only the unambiguous identifier shape is exempt.
# Deliberately NOT a backtick/fence exemption: backticked spans are where an agent would paste a
# discovered credential, so exempting them would hollow the guard.
CAMELCASE_RE = re.compile(r"^[a-z]+(?:[A-Z][a-z]+)*(?:[A-Z]{2,6})?$")

# Inline "this is not a real secret" marker (detect-secrets convention). Suppresses Stage-2
# entropy and low-confidence generic shapes on its line only — it can NOT silence a Stage-1 named
# key format (see the scan loop): named-key formats must be redacted, not pragma'd, because the
# pragma is agent-authored content and thus a smuggling channel.
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
        pragma = bool(PRAGMA_RE.search(line))
        # Stage 1: labeled patterns. Named high-confidence key formats run on EVERY line
        # regardless of the pragma — named-key formats must be redacted, not pragma'd, because
        # the pragma is agent-authored content and thus a smuggling channel. The pragma still
        # suppresses low-confidence generic shapes here and the Stage-2 entropy gate below.
        for category, rx, high_confidence in PATTERNS:
            for m in rx.finditer(line):
                value = m.group(m.lastindex) if m.lastindex else m.group(0)
                key = (lineno, value)
                if key in seen:
                    continue
                seen.add(key)
                if not high_confidence:
                    # Generic low-confidence shapes: pragma silences them, else obvious human
                    # placeholders are dropped. High-confidence keys skip both.
                    if pragma or PLACEHOLDER_RE.search(value):
                        continue
                findings.append({"category": category, "detector": "pattern",
                                 "line": lineno, "preview": redact(value)})
        # Stage 2: entropy gate on unmatched long tokens — pragma-suppressed (a backstop, not a
        # named format, so the explicit per-line opt-out still applies).
        if pragma:
            continue
        for m in TOKEN_RE.finditer(line):
            token = m.group(0)
            if (lineno, token) in seen:
                continue
            if PLACEHOLDER_RE.search(token):
                continue
            if CAMELCASE_RE.match(token):
                continue  # letters-only camelCase identifier — see CAMELCASE_RE
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
        if a in ("-h", "--help"):
            sys.stdout.write("usage: secret_scan.py <file-or-\"-\"> [--format text|json]\n")
            return 0
        elif a == "--format":
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
