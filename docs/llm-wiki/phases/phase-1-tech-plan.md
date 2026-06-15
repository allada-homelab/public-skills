# /llm-wiki — Phase 1 Technical Plan

> **Status: ✅ shipped & dogfooded (2026-06-14).** This spec is built and verified; the test corpus
> is green (`pass=10 fail=0 skip=1`) and the loop was dogfooded on this repo. See
> [README.md](../README.md) for overall roadmap status.
>
> Companion to [`PHASE_PLAN.md`](../planning/PHASE_PLAN.md) (phasing) and [`PRODUCT_PLAN.md`](../planning/PRODUCT_PLAN.md)
> (product vision). This is the buildable spec for **Phase 1 only**. Produced via a multi-agent pass
> (scope distill + live Claude Code contract research + OKF rule extraction → 4 component designs →
> adversarial verification → synthesis).
>
> **Contract verification status (orchestrator):** the manifest locations, the `.claude-plugin/`
> placement, the inline-path `source` form, `${CLAUDE_PLUGIN_ROOT}`, the skill auto-activation model,
> and the hook-event list were re-checked against
> [`reference/claude_code_plugin_system.md`](../reference/claude_code_plugin_system.md)
> and hold. The `allowed-tools` Bash glob syntax was **confirmed** against `permissions.md` (the
> trailing `Bash(python3:*)` colon form is a documented equivalent of the space form — see §4). The
> only items left for a live `capture` run are *behavioral*: that the call runs without a permission
> prompt, and that the skill `description` auto-activates on real phrasings.

## 1. Overview

Phase 1 ships the smallest installable plugin that proves the OKF loop end-to-end: a user, inside a
normal Claude Code session, can initialize an OKF v0.1 knowledge bundle, capture a session finding as a
conformant concept, and read it back via `explore`/`query` — all confirm-first, with no hooks, no MCP,
and no subagents. Conformance is *guaranteed* by a deterministic Doctor script (the pre-write gate and
the on-demand `conform` command), not by the reference Skill, which only makes Claude's first-draft
output near-conformant. A report-only secret scan surfaces planted credentials in every capture diff,
and `explore`/`query` increment a per-concept consultation counter as a seam for later phases. The
portability bar is dual: every captured bundle must render on GitHub **and** pass our own Doctor (the
Google reference-visualizer check is Phase 4, excluded here).

---

## 2. Repository & plugin layout

The repo root **is** the marketplace; the plugin is one entry under `plugins/`.

```
public-skills/                                  (marketplace repo root)
├── .claude-plugin/
│   └── marketplace.json            ← new
├── plugins/
│   └── llm-wiki/                   ← new       (the plugin; inline source target)
│       ├── .claude-plugin/
│       │   └── plugin.json         ← new       (manifest — inside .claude-plugin/, NOT plugin root)
│       ├── commands/               ← new       (flat .md → /llm-wiki:<name>, auto-discovered)
│       │   ├── init.md
│       │   ├── capture.md
│       │   ├── explore.md
│       │   ├── query.md
│       │   └── conform.md
│       ├── skills/
│       │   └── wiki/               ← new       (one model-invocable Skill, auto-discovered)
│       │       ├── SKILL.md
│       │       └── references/
│       │           ├── frontmatter.md
│       │           ├── reserved-files.md
│       │           ├── linking.md
│       │           └── concept-template.md
│       └── scripts/                ← new       (shared deterministic scripts; via ${CLAUDE_PLUGIN_ROOT})
│           ├── doctor.py
│           ├── secret_scan.py
│           └── fixtures/                       (the proof corpus — §5)
├── CLAUDE.md  ·  LICENSE  ·  README.md  ·  docs/llm-wiki/reference/
```

**Placement rules (hard, from the verified contract):**
- Both manifests live in a `.claude-plugin/` directory; `.claude-plugin/` holds *only* its manifest.
  Component dirs (`commands/`, `skills/`, `scripts/`) live at the **plugin root**, never inside
  `.claude-plugin/`.
- No `hooks/`, `.mcp.json`, `agents/`, `monitors/`, or `settings.json` anywhere — their absence is what
  structurally enforces the Phase 1 non-goals.
- Five flat `commands/*.md` → five `/llm-wiki:<name>` commands. One `skills/wiki/` dir → one
  model-invocable skill, namespaced `llm-wiki:wiki` (the namespace derives from the **directory name**
  `wiki/`, per the skills-doc name-derivation table — *not* from frontmatter `name`).

### `plugins/llm-wiki/.claude-plugin/plugin.json`

```json
{
  "name": "llm-wiki",
  "version": "0.1.0",
  "description": "Capture and query a curated OKF v0.1 knowledge bundle from inside a Claude Code session — init, capture, explore, query, conform, all confirm-first.",
  "author": { "name": "David Allada", "email": "davidanilallada@gmail.com" },
  "license": "MIT",
  "keywords": ["okf", "knowledge", "wiki", "open-knowledge-format"]
}
```

`name` is the load-bearing field (kebab-case; becomes the `/llm-wiki:` namespace). **No `commands`/`skills` keys** — that keeps plain auto-discovery
(setting `commands` would *replace* the default location; setting `skills` would *add* to it). No
`hooks`/`mcpServers`/`monitors` — Phase 1 non-goals enforced by omission.

> **Post-Phase-1 (don't scaffold the `version` line above):** the shipped manifest no longer pins
> `version` — omitting it makes Claude Code fall back to the git commit SHA, so every commit
> auto-updates installs — and adds the optional `$schema` field for editor validation. Rationale in the
> [`plugin-versioning`](../../../llm-wiki/plugin-versioning.md) concept.

### `public-skills/.claude-plugin/marketplace.json`

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "public-skills",
  "description": "David Allada's public Claude Code marketplace.",
  "owner": { "name": "David Allada", "email": "davidanilallada@gmail.com" },
  "plugins": [
    {
      "name": "llm-wiki",
      "description": "Capture and query a curated OKF v0.1 knowledge bundle from inside a Claude Code session.",
      "category": "knowledge",
      "source": "./plugins/llm-wiki"
    }
  ]
}
```

**SHA-pin note.** The `github`-object-with-`path` form does not exist on the verified contract: the
`github` source type accepts only `repo`/`commit`/`sha` — no `path` field — so it would fetch the repo
root and never find the plugin manifest under `plugins/llm-wiki/`. The locked-scope form avoids this
entirely: a **bare inline path string** `"./plugins/llm-wiki"`. This is the documented same-repo form;
the SHA pin is **intrinsic** — the user installs the marketplace repo *at a commit*, so the plugin
subtree is pinned to that same commit by construction. No `repo`/`ref`/`sha` fields to hand-maintain.
`plugin.json`'s explicit `version` remains the human-readable release marker; there is no second SHA knob.

### `${CLAUDE_PLUGIN_ROOT}` contract
Commands/Skill address the shared scripts only via `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` (expanded by
Claude Code, valid in markdown bodies; the absolute install path is unknown at authoring time and the
user's cwd is the bundle). `scripts/` is *not* an auto-registered component surface — it is a library
reached only through that variable.

---

## 3. The OKF reference Skill

**Role boundary (stated everywhere it matters):** the Skill makes conformant output *likely* (prose in
a probabilistic model); **Doctor makes it guaranteed** (deterministic code, the pre-write gate). If
Skill and Doctor disagree, Doctor wins, and the Skill's own text says so. Changing the Skill never
changes what conforms — only first-pass draft quality (fewer Doctor round-trips).

### `skills/wiki/SKILL.md` frontmatter

```yaml
---
name: wiki
description: >-
  Build, maintain, and read a project knowledge wiki — a curated library of
  markdown notes the agent consults to start each session smarter. This skill
  should be used when the user wants to capture or save a finding, decision,
  runbook, schema, or metric into a wiki or knowledge base; or to initialize,
  explore, or query that wiki. The wiki follows the Open Knowledge Format
  (OKF v0.1); this skill explains its conformance and concept/frontmatter/linking
  rules so authored files are near-conformant before the deterministic Doctor
  gate runs. Also relevant when the user mentions llm-wiki, OKF, a concept doc,
  index.md, or log.md.
---
```

- **`description`** is the only auto-activation signal: third-person voice (required by the live skills
  doc), and **intent-first** — it leads with plain "build/read a project knowledge wiki" and "capture a
  finding" so triggering never depends on the model recognizing the (new) "OKF" acronym; OKF jargon
  (`index.md`, `log.md`, concept) is a secondary signal, and the Doctor-boundary clause biases retrieval
  away from treating the Skill as the validator.
- **`name: wiki`** is the display label in skill listings. The invocation/namespace name `llm-wiki:wiki`
  derives from the **`skills/wiki/` directory name**, not this field (renaming the directory *would*
  change the command name regardless of `name`).
- No `disable-model-invocation` (auto-activation is the point), no per-skill `tags`/`version` (unearned).

### SKILL.md body (lean — ~one screen) and `references/`

Body carries only what Claude must hold for every OKF action:
1. **Mental model (3–4 sentences):** a bundle is a dir of markdown; one file = one concept; the file
   path minus `.md` is the concept's identity (no ID field); concepts cross-link as ordinary markdown
   forming a graph; `index.md`/`log.md` are reserved and are never concepts.
2. **The three hard rules as authoring constraints** — R1 parseable frontmatter on every concept;
   R2 non-empty `type`; R3 reserved-file structures (subdir `index.md` zero frontmatter, root `index.md`
   only `okf_version: "0.1"`, `log.md` newest-first with ISO `YYYY-MM-DD` headings and bold
   `**Creation**`/`**Update**`/`**Initialization**` prefixes). Stated verbatim-faithful to Doctor's R1/R2/R3.
3. **Boundary statement:** "These rules guide what you write; they do not verify it. Every authored file
   is checked by the deterministic Doctor in strict-producer mode before the confirm diff. Doctor is the
   authority — if your draft and Doctor disagree, Doctor is right. Never claim conformance on these
   instructions alone."
4. **Permissive-consumer principle (one line):** when *reading* (explore/query), tolerate missing
   optional fields, unknown `type`, unknown keys, missing `index.md`, broken links — never refuse to
   read. (Phase 1 this is a reading instruction to Claude; the enforced lenient-consumer Doctor mode is
   Phase 4.)
5. **Pointers into `references/`** (load-on-demand, not duplicated in the body):

| Reference file | Carries | Spec basis |
|---|---|---|
| `frontmatter.md` | `type` (required, non-empty, any string); the five recommended keys (`title`, `description`, `resource`, `tags`, `timestamp`) with types + ISO-8601 example; custom keys allowed, unknown keys preserved | §3 |
| `reserved-files.md` | exact `index.md` body shape; root-vs-subdir frontmatter distinction; exact `log.md` shape (newest-first, `## YYYY-MM-DD`, bold prefixes) with a two-entry example | §6, §9 |
| `linking.md` | bundle-relative (`/x.md`) vs relative (`./x.md`); undirected edges, relationship conveyed in prose; broken links tolerated on read | §5 |
| `concept-template.md` | copy-paste conformant skeleton aligned to the GOOD fixture, so a captured concept passes Doctor first try | §3, §7, fixtures |

6. **Command map (orientation, not reimplementation):** one line each for init/capture/explore/query/conform
   — does *not* restate args, `allowed-tools`, or Doctor internals (those are owned by their components;
   restating invites drift).

A read-only `query`/`explore` loads none of the authoring references; a `capture` loads
`concept-template.md` (and `frontmatter.md`/`linking.md` on demand). The Skill never dumps the raw
`okf_spec.md` into context.

---

## 4. Command contracts

**Shared invariants (all five):**
- **Confirm-first:** no file is created/modified without first showing the exact proposed change (full
  content for new files; unified diff for edits) and receiving explicit affirmative. `explore`/`query`
  are read-only *except* the counter increment, itself confirm-gated.
- **Bundle-root resolution:** explicit `--bundle <path>` → else the default bundle location
  `${CLAUDE_PROJECT_DIR}/llm-wiki` (if it holds a root `index.md` with `okf_version: "0.1"`) → else walk
  up from the cwd for such an `index.md`. None found → `init` offers to create; the other four fail with
  "No OKF bundle here. Run `/llm-wiki:init` first." (Default bundle dir is `llm-wiki/`, per the product plan.)
- **Consultation counter:** `<bundle-root>/.llm-wiki/consultations.json` (a dotdir non-`.md`, invisible
  to Doctor and OKF consumers — never affects conformance or GitHub-render). Phase 1 only increments.
- **`allowed-tools` Bash scoping:** the pattern matches the **stable command head**, not the volatile
  post-expansion absolute path (Claude expands `${CLAUDE_PLUGIN_ROOT}` *before* the Bash call, so a
  literal-`${CLAUDE_PLUGIN_ROOT}` pattern can never match). Form used: `Bash(python3:*)`.
  > **✓ Resolved (confirmed against `permissions.md`):** the workflow's claim that the colon-glob is
  > "undocumented" was wrong. The official permissions doc states the trailing `:*` suffix is an exact
  > equivalent of the space form (`Bash(ls:*)` == `Bash(ls *)`), valid only at the *end* of a pattern.
  > The implementation uses `Bash(python3:*)`. What still needs a live `/llm-wiki:capture` run is only
  > whether the call actually executes *without* a permission prompt (behavior), not the syntax.

**Doctor invocation contract assumed by writing commands (bundle mode):**
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --mode strict --format json <tmp-bundle-mirror>
```
A single-file gate would skip all R3 checks, letting a malformed regenerated `index.md` or out-of-order
`log.md` append slip through. Instead, writing commands stage **all** pending artifacts into a `/tmp`
bundle mirror that reproduces their bundle-relative paths (so root-vs-subdir `index.md` and `log.md`
order resolve correctly), run Doctor in **bundle mode** over the mirror, then delete it. No bundle file
is touched until after the gate passes *and* the user confirms.

---

### `/llm-wiki:init` — bootstrap an empty conformant bundle (one-time)
- **Args:** `$ARGUMENTS` (optional target path; default `${CLAUDE_PROJECT_DIR}`). Domain-pack choice is
  an interactive prompt, not an arg.
- **allowed-tools:** `Glob`, `Read`, `Write`, `Bash(python3 *)`. No `Edit` (creates only), no secret
  scan (writes only fixed boilerplate).
- **Confirm-first flow:** resolve target → Glob for an existing root `index.md`; if present, refuse
  ("bundle already exists; use capture"). → prompt for optional domain-pack subdir → compose file set in
  memory → stage to `/tmp` mirror, run Doctor bundle-mode gate (catches a regression in init's own
  boilerplate) → show full content of every new file → on confirm, Write each (root `index.md` first; if
  it fails, stop — no partial bundle).
- **Files touched (on confirm):** `<target>/index.md` (frontmatter exactly `okf_version: "0.1"`),
  `<target>/log.md` (`# Directory Update Log`, then `## 2026-06-14` / `* **Initialization**: Bundle
  created.`), optional `<target>/<pack>/index.md` (zero frontmatter).
- **Doctor gate:** bundle-mode over the staged files; non-zero → abort with violations verbatim, write
  nothing.

### `/llm-wiki:capture` — finding → one conformant concept (the heart of the loop)
- **Args:** `$ARGUMENTS` (optional free-text title/finding hint; if empty, derive from session context
  and confirm the subject), `--bundle <path>`.
- **allowed-tools:** `Glob`, `Grep`, `Read`, `Write`, `Edit`, `Bash(python3 *)` (Doctor + secret scan).
- **Phase 1 scope guard:** capture targets the **bundle root directory only** — no subdirectory
  creation. This keeps the single regenerated `index.md` always reachable from `explore`'s root walk
  (a concept captured into a new subdir would leave the root index with no pointer down to it, silently
  breaking retrieval). Subdir capture + bounded ancestor-index linking is deferred to Phase 2.
- **Confirm-first flow:**
  1. Resolve bundle root; none → fail.
  2. Determine `type` + `title` + root-level slug from args/session context.
  3. **Duplicate check** (Grep `title`/`resource`/normalized slug + Glob the path). Strong match →
     refuse, name the existing Concept ID, offer refine hand-off (refine itself is Phase 2). No write.
  4. Compose the three pending artifacts: the new concept; the regenerated **root** `index.md`; the
     appended `log.md` **Creation** entry.
     - **Cross-link:** require a cross-link to a related existing concept **only when one exists**. On an
       effectively-empty bundle (first capture), allow zero cross-links and say so in the diff ("no
       related concept yet; no cross-link added"). A report-only link-resolution pass over the pending
       concept's outbound links runs against the staged mirror; any dangling link is surfaced in the
       confirm diff as a WARNING (Doctor itself does not walk links in Phase 1).
     - **log.md / index.md shapes:** the capture-created-or-appended `log.md` is byte-aligned to init's
       template (`# Directory Update Log` H1, then `## YYYY-MM-DD` blocks). Index bullets and the log
       entry both use **relative `./x.md` links** (Q1 — decided). Index regeneration is a full deterministic rewrite of
       the root index, but **preserves any existing sibling row it cannot confidently re-derive** rather
       than dropping/mangling it — a sibling row changes only if that sibling's frontmatter actually
       changed; all such changes appear in the confirm diff.
  5. **Doctor pre-write gate (strict, bundle mode over the /tmp mirror):** validates the new concept
     *and* the regenerated index (R3b) *and* the appended log (R3c order/format/prefix). Non-zero →
     abort, print violations verbatim, write nothing.
  6. **Secret scan (report-only):** `secret_scan.py` over the pending concept body + the log bullet.
     Findings collected, **never blocking**.
  7. **Confirm diff:** full content for the new concept; unified diff for the regenerated index and the
     log append; any secret-scan hits rendered as a prominent "Potential secrets detected (review before
     confirming)" block; any dangling-link WARNING.
  8. On confirm → Write concept, Write regenerated index, Edit log append (order: concept → index → log;
     if a later write fails, report exactly which landed — fail loud, no silent rollback). On decline →
     clean no-op.
- **Date source:** UTC date at capture time; the log-order R3c check in the bundle-mode gate catches an
  out-of-order insert.

### `/llm-wiki:explore` — progressive-disclosure navigation
- **Args:** `$ARGUMENTS` (optional start subpath; default root), `--bundle <path>`.
- **allowed-tools:** `Glob`, `Read`, `Write` (Write scoped *only* to `.llm-wiki/consultations.json`).
  No `Grep` (that's `query`), no `Edit`, no Doctor, no secret scan.
- **Flow:** read the starting `index.md`, present its bullets (titles + descriptions, no full bodies —
  the lean-context win); user picks a subdir index → recurse, or a concept → Read and present (each
  concept opened counts for the counter). Missing `index.md` at a level → fall back to Glob-listing
  `*.md` and continue (consumer-tolerant; never abort). Broken link → report inline, keep navigating.
- **Counter (confirm-first):** before exit, propose the increment deltas and write on confirm; decline →
  results stand, counter untouched.

### `/llm-wiki:query` — grounded answer with citations + gap flag
- **Args:** `$ARGUMENTS` (**required** question; empty → prompt, no guessing), `--bundle <path>`.
- **allowed-tools:** `Glob`, `Grep`, `Read`, `Write` (counter only). No `Edit`, no Doctor, no secret scan.
- **Flow:** locate entry points (Grep key terms + read root `index.md`) → traverse minimally, following
  cross-links that bear on the question → **answer only from content actually read**, every claim cites
  its Concept ID / bundle-relative path, end with a `Sources:` list. A concept "counts" when its body is
  actually Read (index files don't count).
- **Gap flag (required):** if no concept answers, state "The wiki does not contain an answer to this,"
  emit a structured line `GAP: <question> — no concept covers <topic>. Consider /llm-wiki:capture to add
  it.`, and do not fabricate. A query can be partly answered + partly a gap. Phase 1 only *reports* the gap.
- **Counter (confirm-first):** as `explore`; corrupt/missing counter file → fail soft (treat as `{}`),
  never break the answer.

### `/llm-wiki:conform` — on-demand Doctor report
- **Args:** `$ARGUMENTS` (optional bundle/file path; default `${CLAUDE_PROJECT_DIR}`); optional `--json`.
- **allowed-tools:** `Glob`, `Read`, `Bash(python3 *)`. **No `Write`/`Edit`** — read-only report.
- **Flow:** resolve target → run `doctor.py <path> --format text` (or `--format json` if requested) →
  print the result verbatim → no writes, ever.
- **Doctor gate / failure:** this command *is* the user-facing Doctor surface; exit `0` → PASS report,
  exit `1` → FAIL report with findings, exit `2` (operational error) → surface verbatim.

---

## 5. The Doctor script

One Python 3 **stdlib-only** script (`re`, `datetime`, `json`, `sys`, `pathlib`, `glob`) — no PyYAML, no
Node, no install step. Frontmatter is parsed by a ~30-line **restricted parser** (accepts blank/`# comment`
lines, `key: value` scalars, and `key:` + indented `  - item` lists); any other shape (nested maps, flow
`{}`/`[]`, unterminated quote, tab indent, non-`---`-terminated block) returns `UNPARSEABLE` → reported
as **R1**. This fails closed, which is correct because strict-producer Doctor only ever validates files
the plugin itself authored plus controlled fixtures.

**File classification** (by name + location): root `index.md` / subdir `index.md` / `log.md` / concept
(every other `*.md`). Each kind runs only its checks. **ERROR** counts toward non-zero exit; **WARNING**
is reported but never changes exit code.

### Rule set (with reserved-file structures)

| Kind | Rule | Check | Result |
|---|---|---|---|
| Concept | **R1** | first line `---`, block closes, parser ≠ `UNPARSEABLE` | fail → ERROR R1 |
| Concept | **R2** | `type` key present, value non-empty after trim + quote-strip (evaluated only if R1 passed, to avoid double-reporting one root cause) | absent/empty → ERROR R2 |
| Root `index.md` | **R3b** | frontmatter optional; if present, key set ⊆ `{okf_version}`; any other key → ERROR R3b. **`okf_version` present but ≠ `"0.1"` → ERROR R3b** (a producer only ever emits `"0.1"`; best-effort-on-unknown-version is a *consumer* tolerance reserved for Phase 4 lenient mode). Present-but-`UNPARSEABLE` → ERROR R3b. |
| Subdir `index.md` | **R3a** | must have zero frontmatter; any `---` block at all (parseable or not) → ERROR R3a |
| `log.md` | **R3c-date** | every `## ` heading matches `^\d{4}-\d{2}-\d{2}$` and is a real date (`date.fromisoformat`) | fail → ERROR R3c (quotes the heading) |
| `log.md` | **R3c-order** | valid heading dates are non-increasing (equal allowed); evaluated only over date-format-valid headings | first ascending pair → ERROR R3c |
| `log.md` | **R3c-prefix** | every `* ` bullet begins with exactly one of `**Update**` / `**Creation**` / `**Initialization**` | fail → ERROR R3c (names the date block) |

`okf_version` in a subdir index or concept → WARNING (meaningful only at root). Index/log **body
conventions** (descriptions on bullets) are not enforced in Phase 1 (spec marks them "should"; index
bodies are plugin-generated). **Cross-links are not walked** by Doctor in Phase 1 — broken links are
WARNING-only by spec, earn no exit criterion, and add a resolution surface; the capture command's own
report-only link pass covers the one place a dangling link matters. The `F-BL` fixture is retained but
`skip`-marked as a documented Phase 4 seam.

### Modes (strict ⊄ lenient — locked-scope requirement)
```
doctor.py <bundle-or-file-path> [--mode strict|lenient] [--format text|json]
```
- `--mode strict` (default): all checks above. Runs as a **separate top-level branch** that reads no
  consumer-tolerance flag, so it can never silently inherit a Phase 4 tolerance.
- `--mode lenient`: **Phase 1 stub** — prints `lenient consumer mode is not implemented in Phase 1
  (deferred to Phase 4)` to stderr, exits `2`. The flag freezes the contract so callers can be written
  against it now.
- A **single index.md must never be validated via a bare single-file path** (its root-vs-subdir rule is
  undecidable without bundle context). The capture/init gate always runs bundle-mode over the /tmp
  mirror, which gives Doctor the root context to classify correctly.

### Report-only secret scan (`secret_scan.py` — separate file, separate exit contract)
```
secret_scan.py <file-or-"-"> [--format text|json]
```
Reads one pending payload (path or `-` for stdin, so capture can scan content it hasn't written).
**Always exits `0` in Phase 1** regardless of findings — commands surface findings in the confirm diff;
the human decides. (Phase 3 re-wires the *caller*/`PreToolUse` hook to treat findings as blocking; the
script is unchanged.)
- **Stage 1 — labeled-pattern regexes** (high precision): cloud keys (`AKIA…`/`ASIA…`, `AIza…`, GCP SA
  private-key blocks), API tokens (`xox[baprs]-…`, `gh[pousr]_…`, `sk-…`/`sk-ant-…`, bearer in
  `Authorization:`), PEM private-key blocks, connection strings with inline creds
  (`scheme://user:password@host`, JDBC `password=`), and assignment-shaped secrets
  (`(password|secret|token|api[_-]?key)` + entropy-passing value).
- **Stage 2 — entropy gate** (recall): for unmatched tokens ≥ 20 chars, Shannon entropy ≥ **4.0
  bits/char** *and* ≥2 charset classes (suppresses prose). The threshold is a single named constant —
  the one tunable knob; report-only posture makes a false positive cost one glance.

### Output contract (frozen for Phase 1)
- **Exit codes:** `0` = validated, zero ERRORs (warnings allowed); `1` = ≥1 ERROR; `2` =
  usage/operational error (bad path, unreadable file, `--mode lenient`, bad flag). Callers gate on exit
  code alone.
- **`--format json`** — single object on stdout: `{ "schema": "okf-doctor/1", "mode", "target", "ok",
  "summary": {errors,warnings,files_checked}, "findings": [{severity,rule,file,line,message}] }`.
  `ok == (errors==0)`. `rule ∈ {R1,R2,R3a,R3b,R3c}`; `file` bundle-relative when a root was given; `line`
  best-effort. **Determinism is a hard requirement** — findings sorted by `(file, line, rule)`, file walk
  `sorted()`, no mtime/hashmap/locale dependence → identical input bytes ⇒ byte-identical JSON.
- **`--format text`** (default) — human lines `ERROR  R2   tables/x.md:2   message`, ending
  `Result: PASS|FAIL — N errors, M warnings`. Warnings render as `WARN`, never change exit.
- **secret-scan JSON** mirrors the envelope (`schema: "okf-secret-scan/1"`, findings carry `category`,
  `detector ∈ {pattern,entropy}`, `line`, and a **redacted** preview — first 4 chars + `…`, never the
  full secret).

### Fixture set (the proof corpus = the test suite)
Under `scripts/fixtures/`. Each malformed fixture is a *minimal complete bundle* (root `index.md` +
`log.md` + the one offending file) so it's valid except for the single planted violation. A
`run_fixtures.sh` harness (bash — zero-dep, holds the dependency-light bar) runs `doctor.py … --format
json` per fixture and exact-diffs against a frozen `expected/<name>.json`, asserting the exit code too
(exact diff is possible *because* output is deterministic).

| Fixture | Planted defect | Expected |
|---|---|---|
| `good/` | fully conformant minimal bundle (root index `okf_version` only; subdir index no frontmatter; concept with `tags:` list + quoted `type`; 2-entry newest-first log) | exit `0`, 0 errors |
| `r1_no_frontmatter` | concept, no `---` block | ERROR R1 |
| `r2_missing_type` | concept frontmatter without `type` | ERROR R2 |
| `r2_empty_type` | `type: ""` | ERROR R2 |
| `r3a_subdir_index_frontmatter` | subdir `index.md` with a `---` block | ERROR R3a |
| `r3b_root_index_extra_key` | root index with `okf_version` + `title` | ERROR R3b (disallowed key `title`) |
| `r3c_log_ascending` | log dates oldest-first | ERROR R3c (order) |
| `r3c_log_bad_dateformat` | `## May 22, 2026` | ERROR R3c (date format) |
| `r3c_log_missing_prefix` | bullet without a bold prefix | ERROR R3c (prefix) |
| `secret/` | conformant concept with a planted `AKIA…`-shaped key in a code block | Doctor **passes**; `secret_scan.py` emits ≥1 finding |
| `F-BL` (skip) | concept with a dangling `/tables/customers.md` link | Phase 1: no Doctor error (documented Phase 4 seam) |

The harness's pass/fail **is** the Doctor exit-criteria proof. The `good/` fixture's concept deliberately
exercises a `tags:` list and a quoted `type` — the seam to watch is whether any frontmatter shape
`capture` legitimately authors could be mis-flagged `UNPARSEABLE` (R1); if capture's real output exceeds
flat scalars + simple lists, widen the parser grammar and add a fixture *before* that shape ships.

---

## 6. Phase 1 exit-criteria checklist (runnable, dogfooded on public-skills)

Run top to bottom; the loop "exists" only when all pass. Dogfood target is this repo.

**A. Doctor proof (offline, before any install):**
1. `python3 plugins/llm-wiki/scripts/fixtures/run_fixtures.sh` → `good/` exits `0`; all 8 malformed
   fixtures exit `1` on their named rule; `secret/` shows Doctor PASS **and** ≥1 secret finding; `F-BL`
   is a no-op. ☐

**B. Install + discovery:**
2. `/plugin marketplace add allada-homelab/public-skills` (real slug; or add the local path during
   dogfood) → marketplace.json parses, `plugins[0].name == "llm-wiki"` matches the manifest. ☐
3. `/plugin install llm-wiki@public-skills` → exactly **five** commands + **one** skill appear under the
   `llm-wiki:` namespace; no `hooks/`/`.mcp.json`/`agents/` anywhere. ☐

**C. The loop, on this repo (each step confirm-first, each write logged):**
4. `/llm-wiki:init` → creates the default `llm-wiki/` bundle: root `index.md` (`okf_version` only), `log.md`
   (`**Initialization**`), shown and confirmed before write. ☐
5. `/llm-wiki:capture` a **real public-skills finding** — proposed proof artifact: *"OKF Doctor
   strict-producer rule set (R1/R2/R3a–c)"* as a concept of `type: Reference`. First capture into a
   fresh bundle → zero cross-links, stated in the diff; Doctor bundle-mode gate passes with zero
   violations; concept + regenerated root index + `log.md` **Creation** entry shown and confirmed. ☐
6. **Secret scan:** re-run capture (or a sibling capture) with a **planted `AKIA…` credential** in the
   draft body → the confirm diff shows the "Potential secrets detected" block; the write is *not* blocked
   (report-only). ☐
7. `/llm-wiki:query "what does our wiki say about Doctor's R3 rules?"` → answer grounded only in the
   captured concept, with a `Sources:` citation to its path; counter increment proposed + confirmed. ☐
8. `/llm-wiki:query` an unknown topic → emits the `GAP:` line, no fabrication. ☐
9. `/llm-wiki:conform <bundle>` → `Result: PASS — 0 errors`. ☐

**D. Portability bar (dual — GitHub-render + Doctor; Google visualizer excluded):**
10. **Doctor half:** step 9 PASS. ☐
11. **GitHub-render half:** push the dogfood bundle; on GitHub confirm (a) the concept renders, (b) its
    cross-link (once a second concept exists) is clickable/resolves, (c) `index.md`/`log.md` render
    cleanly. Capture emits **relative `./x.md`** links (Q1 — decided), which resolve on GitHub. ☐

---

## 7. Implementation decisions (resolved)

**Q1 — Link form → relative `./x.md` (LOCKED).** Capture emits relative `./x.md` links (in concepts,
index bullets, and `log.md`). Relative is an OKF-valid form *and* resolves on GitHub's blob view, so it
satisfies both halves of the dual portability bar with no caveat and removes the index-vs-log link
inconsistency. (Bundle-relative `/x.md` was rejected because a leading-`/` link does not resolve on
GitHub.)

**Q2 — Capture scope → root-only for Phase 1 (LOCKED).** Capture creates concepts in the bundle root
directory only, so every concept stays reachable from `explore`'s root-index walk (a subdir concept
would orphan from the root index and silently break retrieval). Bounded subdir capture + the
root-index→subdir-index linking update is deferred to Phase 2.

**Q3 — Fixture harness → bash `run_fixtures.sh` (LOCKED).** Zero dependencies, holds the
dependency-light bar. Revisit pytest only if the plugin gains a Python test suite for other reasons.

**Q4 — Secret-scan defaults → entropy 4.0 bits/char, min token len 20 (ship as-is).** Sane for
report-only Phase 1 (a false positive costs one glance). These will be **retuned in Phase 3** when the
script becomes a blocking `PreToolUse` hook — not treated as final.

---

## Verification disposition & live-confirm items

All three HIGH cc-contract / conformance findings are applied (source form + slug, capture bundle-mode
gate, cross-link conditionality). The orphaned `conform` command is fully specified (§4). The
`okf_version`-mismatch consumer-tolerance leak is fixed to ERROR in strict mode. Deferred finding: live
link-walking inside Doctor — kept out (report-only link check lives in capture instead); the `F-BL`
fixture preserves the Phase 4 seam.

**Claims requiring live in-session confirmation (only David can verify):**
1. The `allowed-tools` Bash scope actually suppresses the permission prompt on Doctor/scan calls — and
   the colon-vs-space glob form (see §4 note) — verify with one real `/llm-wiki:capture`.
2. The Skill `description` auto-activates on real dogfood phrasings ("save this finding to the wiki") —
   verify by live activation.
