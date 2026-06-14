#!/usr/bin/env bash
# Doctor fixture harness — the Phase 1 conformance proof (exit-criteria step A).
# Zero deps beyond python3 (already required by doctor.py). For each fixture bundle,
# runs doctor.py in strict bundle mode and asserts exit code + the set of finding
# signatures (SEVERITY:RULE:bundle-relative-path) against expected/<name>.json.
# Free-text messages and line numbers are intentionally NOT asserted (informational).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(dirname "$HERE")"
DOCTOR="$SCRIPTS/doctor.py"
SECRET="$SCRIPTS/secret_scan.py"
EXP="$HERE/expected"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0; skip=0; failed_names=()

for dir in "$HERE"/*/; do
  name="$(basename "$dir")"
  [ "$name" = "expected" ] && continue
  expfile="$EXP/$name.json"

  if [ ! -f "$expfile" ]; then
    echo "FAIL $name — no expected/$name.json"; fail=$((fail+1)); failed_names+=("$name"); continue
  fi

  if python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("skip") else 1)' "$expfile"; then
    echo "SKIP $name"; skip=$((skip+1)); continue
  fi

  dout="$TMP/$name.doctor.json"
  python3 "$DOCTOR" "$dir" --mode strict --format json >"$dout" 2>/dev/null; code=$?

  sout="$TMP/$name.secret.json"; scode=0; has_secret=0
  sfile="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("secret_scan_file",""))' "$expfile")"
  if [ -n "$sfile" ]; then
    has_secret=1
    python3 "$SECRET" "$dir/$sfile" --format json >"$sout" 2>/dev/null; scode=$?
  fi

  verdict="$(python3 - "$expfile" "$code" "$dout" "$has_secret" "$scode" "$sout" <<'PY'
import json, sys
expfile, code, dout, has_secret, scode, sout = sys.argv[1:7]
code = int(code); has_secret = int(has_secret); scode = int(scode)
exp = json.load(open(expfile))
problems = []

try:
    doc = json.load(open(dout))
except Exception as e:
    print("FAIL: doctor did not emit valid JSON (%s)" % e); sys.exit(1)

got = sorted("%s:%s:%s" % (f["severity"], f["rule"], f["file"]) for f in doc.get("findings", []))
want = sorted(exp.get("rules", []))
if code != exp["exit_code"]:
    problems.append("exit %d != %d" % (code, exp["exit_code"]))
if got != want:
    problems.append("rules %s != %s" % (got, want))
if doc.get("ok") != (doc.get("summary", {}).get("errors", -1) == 0):
    problems.append("ok flag inconsistent with summary.errors")

if has_secret:
    smin = exp.get("secret_min", 1)
    if scode != 0:
        problems.append("secret_scan must always exit 0 in Phase 1 (got %d)" % scode)
    else:
        try:
            sdoc = json.load(open(sout))
            n = len(sdoc.get("findings", []))
            if n < smin:
                problems.append("secret findings %d < %d" % (n, smin))
        except Exception as e:
            problems.append("secret_scan invalid JSON (%s)" % e)

print("FAIL: " + "; ".join(problems) if problems else "OK")
sys.exit(1 if problems else 0)
PY
)"; vcode=$?

  if [ $vcode -eq 0 ]; then
    echo "PASS $name"; pass=$((pass+1))
  else
    echo "FAIL $name — $verdict"; fail=$((fail+1)); failed_names+=("$name")
  fi
done

echo "----------------------------------------"
echo "pass=$pass fail=$fail skip=$skip"
if [ $fail -ne 0 ]; then
  echo "FAILED: ${failed_names[*]}"
  exit 1
fi
echo "ALL FIXTURES PASS"
