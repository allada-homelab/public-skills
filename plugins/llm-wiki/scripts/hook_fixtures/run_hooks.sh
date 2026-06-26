#!/usr/bin/env bash
# Hook/script golden harness (Phase 3). Hooks are command scripts with an
# (env + stdin) -> (stdout + exit code) contract. For each case <name>/:
#   cmd          : "<path-from-plugin-root> [args]"; the token BUNDLE -> the tmp bundle path
#   bundle/      : (optional) copied to a tmp dir, exported as CLAUDE_PROJECT_DIR
#   stdin.json   : (optional) piped to the script on stdin
#   env          : (optional) shell sourced AFTER the default CLAUDE_PROJECT_DIR export — may
#                  `export HOME=BUNDLE/home` or `unset CLAUDE_PROJECT_DIR` to exercise the fallbacks
#                  (BUNDLE token substituted here too)
#   expected.json: { "exit_code": N,         (BUNDLE token substituted in all string fields)
#                    "stdout_equals": "…"          (exact match, optional),
#                    "stdout_contains": ["…", …]    (all must appear, optional),
#                    "stdout_absent":  ["…", …]     (none may appear, optional),
#                    "files_present":  ["…", …]     (paths under the bundle that must exist after, optional),
#                    "files_absent":   ["…", …] }   (paths under the bundle that must NOT exist after, optional)
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
  # event JSON (stdin) may reference the bundle via the BUNDLE token → substitute it too
  stdin=/dev/null
  if [ -f "$dir/stdin.json" ]; then sed "s#BUNDLE#$tmp#g" "$dir/stdin.json" >"$tmp/.stdin"; stdin="$tmp/.stdin"; fi
  envfile=""
  if [ -f "$dir/env" ]; then sed "s#BUNDLE#$tmp#g" "$dir/env" >"$tmp/.env"; envfile="$tmp/.env"; fi

  # run from the plugin root so relative script paths + sibling imports resolve;
  # capture exact stdout to a file (command substitution would strip trailing newlines).
  # default CLAUDE_PROJECT_DIR=tmp, then source the optional per-case env so it can override/unset.
  ( cd "$PLUGIN" && export CLAUDE_PROJECT_DIR="$tmp"; [ -n "$envfile" ] && . "$envfile"; python3 $args ) <"$stdin" >"$tmp/.out" 2>/dev/null; code=$?

  verdict="$(python3 - "$exp" "$code" "$tmp/.out" "$tmp" <<'PY'
import json, os, sys
code = int(sys.argv[2]); out = open(sys.argv[3]).read(); tmp = sys.argv[4]
exp = json.loads(open(sys.argv[1]).read().replace("BUNDLE", tmp))  # BUNDLE token in expectations
probs = []
if code != exp["exit_code"]:
    probs.append("exit %d != %d" % (code, exp["exit_code"]))
if "stdout_equals" in exp and out != exp["stdout_equals"]:
    probs.append("stdout != expected (%r)" % out[:80])
for s in exp.get("stdout_contains", []):
    if s not in out: probs.append("missing %r" % s)
for s in exp.get("stdout_absent", []):
    if s in out: probs.append("unexpected %r" % s)
for f in exp.get("files_present", []):
    if not os.path.exists(os.path.join(tmp, f)): probs.append("missing file %r" % f)
for f in exp.get("files_absent", []):
    if os.path.exists(os.path.join(tmp, f)): probs.append("unexpected file %r" % f)
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
