#!/usr/bin/env bash
# Deterministic drift gate for the public-skills marketplace.
# The recurring bug class here is duplicated prose drifting from code or from its own copies:
# a manifest listing a phantom command, a marketplace description still saying "tested" after the
# plugin switched to "checked", a convention reworded in one of its self-contained copies but not
# the others. This gate turns that class into a red check.
#
# Style-matched to plugins/get-shit-done/scripts/checks.sh: bash, `set -u`, ok()/bad() lines, a final
# PASS/FAILED, exit code = the fail flag. python3 is used as a JSON/text helper only (stdlib).
#
# Run:  bash scripts/drift_check.sh            → expects "PASS" and exit 0.
# The repo root defaults to this script's parent; pass an alternate root as $1 to gate a doctored
# copy (used by the negative test) — e.g.  bash scripts/drift_check.sh /tmp/public-skills-copy
set -u
root="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
fail=0
ok()  { echo "ok:   $1"; }
bad() { echo "FAIL: $1"; fail=1; }

# grep helpers (quiet); operate on a repo-relative path under $root.
has()     { grep -Fq -- "$2" "$root/$1"; }   # $1 file, $2 literal — true if present
hasi()    { grep -Fiq -- "$2" "$root/$1"; }  # case-insensitive literal
hasre()   { grep -Eq -- "$2" "$root/$1"; }   # extended regex

MKT=".claude-plugin/marketplace.json"
PLUGIN_JSON="plugins/llm-wiki/.claude-plugin/plugin.json"

# ---------------------------------------------------------------------------
# 1. Manifest <-> commands (llm-wiki): every command file's <name> is named in the
#    plugin.json description, and the description carries no stale mode language.
# ---------------------------------------------------------------------------
desc=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["description"])' "$root/$PLUGIN_JSON" 2>/dev/null)
if [ -z "$desc" ]; then
  bad "plugin.json: could not read description"
else
  for f in "$root/plugins/llm-wiki/commands/"*.md; do
    name="$(basename "$f" .md)"
    if printf '%s' "$desc" | grep -Fq -- "$name"; then
      ok "plugin.json description names command: $name"
    else
      bad "plugin.json description does not name command: $name"
    fi
  done
  if printf '%s' "$desc" | grep -Fiq -- "confirm-first"; then
    bad "plugin.json description contains stale 'confirm-first'"
  else
    ok "plugin.json description free of 'confirm-first'"
  fi
  if printf '%s' "$desc" | grep -Fq -- "Phase 3"; then
    bad "plugin.json description contains stale 'Phase 3'"
  else
    ok "plugin.json description free of 'Phase 3'"
  fi
fi

# ---------------------------------------------------------------------------
# 2. Marketplace banned drift terms (per-entry descriptions).
# ---------------------------------------------------------------------------
mkt_desc() { python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); print(next(p["description"] for p in m["plugins"] if p["name"]==sys.argv[2]))' "$root/$MKT" "$1" 2>/dev/null; }

gsd_desc=$(mkt_desc get-shit-done)
if [ -z "$gsd_desc" ]; then
  bad "marketplace.json: could not read get-shit-done description"
else
  printf '%s' "$gsd_desc" | grep -Eq -- '\btested\b' \
    && bad "marketplace get-shit-done description contains 'tested' (plugin says 'checked')" \
    || ok "marketplace get-shit-done description free of 'tested'"
  printf '%s' "$gsd_desc" | grep -Fq -- "in the background" \
    && bad "marketplace get-shit-done description contains 'in the background'" \
    || ok "marketplace get-shit-done description free of 'in the background'"
fi

wiki_desc=$(mkt_desc llm-wiki)
if [ -z "$wiki_desc" ]; then
  bad "marketplace.json: could not read llm-wiki description"
else
  printf '%s' "$wiki_desc" | grep -Fq -- "confirm-first" \
    && bad "marketplace llm-wiki description contains 'confirm-first'" \
    || ok "marketplace llm-wiki description free of 'confirm-first'"
  printf '%s' "$wiki_desc" | grep -Fq -- "Phase 3" \
    && bad "marketplace llm-wiki description contains 'Phase 3'" \
    || ok "marketplace llm-wiki description free of 'Phase 3'"
fi

# ---------------------------------------------------------------------------
# 3. Breadcrumb convention identical across its three self-contained copies.
#    The exact strings the model is told to emit must match byte-for-byte everywhere.
# ---------------------------------------------------------------------------
breadcrumb_files=(
  "plugins/llm-wiki/scripts/hook_stop.py"
  "plugins/llm-wiki/commands/capture.md"
  "plugins/llm-wiki/skills/wiki/SKILL.md"
)
breadcrumb_strings=(
  "wiki +1: <title>"
  "wiki ~: <title>"
  "wiki blocked (<doctor|secret>): <path>"
)
for s in "${breadcrumb_strings[@]}"; do
  for f in "${breadcrumb_files[@]}"; do
    if has "$f" "$s"; then
      ok "breadcrumb '$s' present in ${f##*/}"
    else
      bad "breadcrumb '$s' MISSING from $f"
    fi
  done
done

# ---------------------------------------------------------------------------
# 4. Flat-first placement rubric agrees across its three deliberately-duplicated copies.
#    Assert short invariant phrases chosen to survive innocent rewording elsewhere.
# ---------------------------------------------------------------------------
placement_files=(
  "plugins/llm-wiki/skills/wiki/SKILL.md"
  "plugins/llm-wiki/commands/capture.md"
  "plugins/llm-wiki/skills/wiki/references/ingestion.md"
)
placement_phrases=(
  "bundle root"
  "~3+ sibling concepts on"
  "depth 1"
)
for p in "${placement_phrases[@]}"; do
  for f in "${placement_files[@]}"; do
    if has "$f" "$p"; then
      ok "placement phrase '$p' present in ${f##*/}"
    else
      bad "placement phrase '$p' MISSING from $f"
    fi
  done
done

# ---------------------------------------------------------------------------
# 5. Spine pure-logic markers present. Extract the two literal marker strings from
#    the TEST (so they can't drift from what the test extracts by), then require both
#    in the spine. If the spine renames a marker the test would break — this catches
#    it deterministically without running node.
# ---------------------------------------------------------------------------
TEST="plugins/get-shit-done/scripts/spine_logic_test.mjs"
SPINE="plugins/get-shit-done/workflows/gsd.workflow.js"
if [ ! -f "$root/$TEST" ] || [ ! -f "$root/$SPINE" ]; then
  bad "spine markers: $TEST or $SPINE missing"
else
  while IFS= read -r marker; do
    [ -z "$marker" ] && continue
    if has "$SPINE" "$marker"; then
      ok "spine marker present: ${marker:0:40}…"
    else
      bad "spine marker MISSING from gsd.workflow.js: $marker"
    fi
  done < <(python3 - "$root/$TEST" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
for name in ("START", "END"):
    m = re.search(r"const %s = '(.*?)'" % name, text)
    if m:
        print(m.group(1))
PY
)
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "FAILED"
else
  echo "PASS"
fi
exit "$fail"
