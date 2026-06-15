#!/usr/bin/env bash
# bundle_ops golden-file harness (Phase 2). For each case <name>/ with input/,
# expected/ and a cmd file: copy input/ to a tmp bundle, run `bundle_ops.py <cmd>`
# (the literal token BUNDLE in cmd is replaced with the tmp path), then assert the
# resulting tree byte-for-byte equals expected/.
#
# Error cases (operational/usage failures): a case may add an `expect_exit` file
# (the expected non-zero exit code). Then the harness asserts the exit code instead
# of running the tree diff, and — if an `expect_err` file is present — asserts its
# contents appear as a substring of stderr. Cases without `expect_exit` keep the
# original contract (exit 0 + byte-for-byte tree match).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(dirname "$HERE")"
OPS="$SCRIPTS/bundle_ops.py"

pass=0; fail=0; failed_names=()

for dir in "$HERE"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/cmd" ] || continue

  tmp="$(mktemp -d)"
  cp -r "$dir/input/." "$tmp/"
  # shellcheck disable=SC2046
  args="$(sed "s#BUNDLE#$tmp#g" "$dir/cmd")"
  # word-split args intentionally; quoting handled by the harness author
  eval python3 "$OPS" $args >/dev/null 2>"$tmp/.err"; code=$?

  if [ -f "$dir/expect_exit" ]; then
    # error case: assert the exit code (and optional stderr substring), not the tree
    want_code="$(cat "$dir/expect_exit")"
    if [ "$code" != "$want_code" ]; then
      echo "FAIL $name — exit $code != expected $want_code: $(cat "$tmp/.err")"
      fail=$((fail+1)); failed_names+=("$name"); rm -rf "$tmp"; continue
    fi
    if [ -f "$dir/expect_err" ] && ! grep -qF "$(cat "$dir/expect_err")" "$tmp/.err"; then
      echo "FAIL $name — stderr missing '$(cat "$dir/expect_err")': $(cat "$tmp/.err")"
      fail=$((fail+1)); failed_names+=("$name"); rm -rf "$tmp"; continue
    fi
    echo "PASS $name"; pass=$((pass+1)); rm -rf "$tmp"; continue
  fi

  if [ $code -ne 0 ]; then
    echo "FAIL $name — bundle_ops exited $code: $(cat "$tmp/.err")"
    fail=$((fail+1)); failed_names+=("$name"); rm -rf "$tmp"; continue
  fi
  rm -f "$tmp/.err"

  if diff -ru "$dir/expected" "$tmp" >/tmp/ops_diff.$$ 2>&1; then
    echo "PASS $name"; pass=$((pass+1))
  else
    echo "FAIL $name — tree differs from expected:"; sed 's/^/    /' /tmp/ops_diff.$$
    fail=$((fail+1)); failed_names+=("$name")
  fi
  rm -f /tmp/ops_diff.$$; rm -rf "$tmp"
done

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
if [ $fail -ne 0 ]; then
  echo "FAILED: ${failed_names[*]}"
  exit 1
fi
echo "ALL OPS FIXTURES PASS"
