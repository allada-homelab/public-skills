#!/usr/bin/env bash
# Hook/script golden harness (Phase 3). Hooks are command scripts with an
# (env + stdin) -> (stdout + exit code) contract. For each case <name>/:
#   cmd          : "<path-from-plugin-root> [args]"; the token BUNDLE -> the tmp bundle path
#   bundle/      : (optional) copied to a tmp dir, exported as CLAUDE_PROJECT_DIR
#   stdin.json   : (optional) piped to the script on stdin
#   expected.json: { "exit_code": N,
#                    "stdout_equals": "…"          (exact match, optional),
#                    "stdout_contains": ["…", …]    (all must appear, optional),
#                    "stdout_absent":  ["…", …] }   (none may appear, optional)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$(dirname "$(dirname "$HERE")")"   # …/plugins/llm-wiki
pass=0; fail=0; failed_names=()

for dir in "$HERE"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/cmd" ] || continue
  exp="$dir/expected.json"
  if [ ! -f "$exp" ]; then echo "FAIL $name — no expected.json"; fail=$((fail+1)); failed_names+=("$name"); continue; fi

  tmp="$(mktemp -d)"
  [ -d "$dir/bundle" ] && cp -r "$dir/bundle/." "$tmp/"
  args="$(sed "s#BUNDLE#$tmp#g" "$dir/cmd")"
  stdin="$dir/stdin.json"; [ -f "$stdin" ] || stdin=/dev/null

  # run from the plugin root so relative script paths + sibling imports resolve;
  # capture exact stdout to a file (command substitution would strip trailing newlines)
  ( cd "$PLUGIN" && CLAUDE_PROJECT_DIR="$tmp" python3 $args ) <"$stdin" >"$tmp/.out" 2>/dev/null; code=$?

  verdict="$(python3 - "$exp" "$code" "$tmp/.out" <<'PY'
import json, sys
exp = json.load(open(sys.argv[1])); code = int(sys.argv[2]); out = open(sys.argv[3]).read()
probs = []
if code != exp["exit_code"]:
    probs.append("exit %d != %d" % (code, exp["exit_code"]))
if "stdout_equals" in exp and out != exp["stdout_equals"]:
    probs.append("stdout != expected (%r)" % out[:80])
for s in exp.get("stdout_contains", []):
    if s not in out: probs.append("missing %r" % s)
for s in exp.get("stdout_absent", []):
    if s in out: probs.append("unexpected %r" % s)
print("FAIL: " + "; ".join(probs) if probs else "OK"); sys.exit(1 if probs else 0)
PY
)"; vcode=$?
  rm -rf "$tmp"
  if [ $vcode -eq 0 ]; then echo "PASS $name"; pass=$((pass+1))
  else echo "FAIL $name — $verdict"; fail=$((fail+1)); failed_names+=("$name"); fi
done

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
[ $fail -ne 0 ] && { echo "FAILED: ${failed_names[*]}"; exit 1; }
echo "ALL HOOK FIXTURES PASS"
