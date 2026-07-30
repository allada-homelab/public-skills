---
description: Capture or update a finding as one conformant OKF concept (create-or-edit; the core loop).
argument-hint: "[title or finding hint] [--into <subdir>] [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write, Bash(python3:*), Bash(mktemp:*), Bash(rm:*), Bash(date:*)
---

You are running `/llm-wiki:capture`. Turn a finding from the current session into **one** conformant
OKF concept. This command is **upsert (create-or-edit)**: if the target concept file already exists you
**edit it in place** (log-kind `Update`); otherwise you **create** it (log-kind `Creation`) — at the
**bundle root by default**, or in a **subdirectory when there is a clear reason** (see "Decide placement"
below). Use the `wiki` skill for format rules and `references/concept-template.md` for the skeleton.

**Writes always apply directly through the gated engine.** There is no confirm-first path: you draft the
concept, then hand it to `bundle_ops apply`, which stages on a throwaway mirror, regenerates the index,
appends the log, **Doctor-gates** (strict, blocking), and **secret-scans** — and only on a clean gate
does it touch the live bundle. A block leaves the live bundle byte-for-byte untouched. The gate is the
safety net; do not add a per-write prompt — surface the outcome as at most one breadcrumb (step 7),
never a prose recap of what you saved.

> **⚠️ NEVER put a secret in a concept.** No API keys, access keys, tokens, passwords, SSH/PEM
> private keys, or credential-bearing connection strings — **not even as an "example"**. The bundle
> is committed to git; a leaked secret is permanent. Reference secrets by **name/location**, never by
> value. The secret scan in `apply` is a backstop, not a license — keep them out by hand.

Arguments: `$ARGUMENTS` may carry a title/finding hint, an optional `--into <subdir>` (force a target
directory, creating it if needed), and an optional `--bundle <path>`.

Steps:

1. **Resolve the bundle root.** Use `--bundle` if given; else the default `${CLAUDE_PROJECT_DIR}/llm-wiki`
   if it holds a root `index.md` whose frontmatter carries an `okf_version` key (any value — a bundle may
   still declare the legacy `"0.1"` mid-migration and must still be found); else walk up from the cwd for
   one. **None found →
   use the default `${CLAUDE_PROJECT_DIR}/llm-wiki`** — `apply` creates a conformant empty bundle
   (`index.md` + `log.md`) automatically on the first write, so there is nothing to bootstrap by hand.
2. **Decide the concept (create vs. update).** From the hint and session context, determine `type`,
   `title`, and a slug (`<slug>.md`). If the subject is unclear, ask before proceeding. Grep the bundle
   for the title / slug / any `resource`, and Glob the path:
   - **Strong match on an existing concept → this is an _update_.** Read that concept and edit it in place
     (step 5, "update" branch); do **not** create a duplicate.
   - **No match → this is a _create_.** Proceed to placement.
   If the finding is a **gotcha-class** one (a failure→fix, a surprising root cause, a silent footgun, a
   verification gap, a hidden precondition, stale knowledge, or a performance cliff — see
   `references/capture-triggers.md` for the full list), use the gotcha shape in
   `references/concept-template.md`: name what fails, what works, and *why*, so it is not repeated.
3. **Decide placement (create only; deterministic root fallback).** Choose the target directory for `<slug>.md`:
   - If `--into <subdir>` was given, use it — validate it stays inside the bundle (no `../` escape, no
     reserved names), creating intermediate dirs.
   - Otherwise pass existing catalog section paths plus this finding's touched/Verify/resource paths to
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/topology.py" select --sections-json '<json>'
     --paths-json '<json>'`. A unique longest full section-token match may select an **existing** section;
     ambiguous/no match returns `{"section":""}` and means bundle root. Never create a section from
     inference; use `/llm-wiki:reorganize` once a real cluster forms.
   (For an _update_, the path is fixed — the concept stays where it is; renames/moves go through
   `/llm-wiki:reorganize`.)
4. **Compose the concept content** (full file bytes — `apply` lands exactly what you write, nothing more):
   - **Create:** from the template; relative `./` links; a non-empty `type`. Cross-link to a related
     existing concept only if one exists; on the first capture into an empty bundle, add no cross-link. For
     a **code-grounded** finding, include a `## Verify` `file:symbol` anchor and stamp a `verified:` mapping
     `{ by: <actor>, at: <UTC datetime> }` — actor `process:llm-wiki-verifier` for this capture-time
     re-confirmation, or `human:<id>` if a human directly confirmed it — with `at` the current full UTC
     datetime `YYYY-MM-DDThh:mm:ssZ` (`date -u +%Y-%m-%dT%H:%M:%SZ`, matching
     `references/concept-template.md`); omit both for a genuinely non-code-verifiable finding. **Never write
     `generated:`** — `apply` stamps it (step 6).
   - **Update:** apply the user's change to the existing concept's body and/or frontmatter, **preserve a
     non-empty `type`**, keep links in the relative `./` form. If the change alters a fact the concept's
     `## Verify` anchor covers, update the anchor too and **append a new `verified:` mapping entry**
     `{ by: process:llm-wiki-verifier (or human:<id>), at: <UTC datetime> }` (the current full UTC datetime
     `YYYY-MM-DDThh:mm:ssZ` via `date -u +%Y-%m-%dT%H:%M:%SZ`) — a capture that re-confirms a fact is the
     point at which it was last verified; keep prior entries as the verification history. Do not touch
     `generated:` — `apply` leaves it as-is when already present and only stamps it when absent.
5. **Write the composed content to a unique temp file** outside the bundle. Mint the path with
   `tmp=$(mktemp /tmp/llm-wiki-capture-XXXXXX.md)` (a fixed path can collide with a concurrent background
   `wiki-capturer`), then Write the bytes to `$tmp` with the Write tool. This file is the exact bytes
   `apply` will gate and commit.
6. **Apply through the gated engine.** Run, with `<relpath>` the concept's bundle-relative path,
   `<Creation|Update>` chosen by the create-vs-update branch from step 2, and a linked-title log message
   (`"Added [<title>](./<relpath>)."` for a create, `"Refined [<title>](./<relpath>)."` for an update, to
   match the existing log style). Pass `--generated-by llm-wiki/<model>` naming the model you're running as
   (for example `--generated-by llm-wiki/claude-opus-5`) so a `generated:` `apply` has to stamp (only when
   the content omits it) attributes to the actual producer instead of the `llm-wiki/unknown` default:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bundle_ops.py" apply "<bundle>" --concept "<relpath>" --content-file "$tmp" --log-kind <Creation|Update> --log-message "<Added|Refined> [<title>](./<relpath>)." --generated-by "llm-wiki/<model>"
   ```

   `apply` owns staging, index regen, log append, the Doctor gate, the secret scan, the commit, and
   auto-migrating any legacy v0.1 fields the bundle still carries (`timestamp` → `generated`, scalar
   `verified` → `{ by, at }`), logging that migration once — do **not** re-author or `cp` the file yourself.
   It prints a one-line JSON status to stdout. Branch on it:
   - **`applied`** (exit 0) → done. The concept, index, and log are committed; surface the one-line
     breadcrumb (step 7) — never a prose recap of the body.
   - **`blocked:doctor`** (exit 1) → the draft is non-conformant and **nothing was written**. Show the
     Doctor violations (on stderr) verbatim, fix the draft, and re-run `apply`. The Doctor wins — if your
     draft and the Doctor disagree, the Doctor is right.
   - **`blocked:secret`** (exit 1) → the secret scan flagged a credential and **nothing was written**.
     Report the redacted finding, strip the secret (reference it by name/location instead), and re-run.
     Two sub-cases: if the flag is a **false positive on a genuinely non-secret high-entropy string** (a
     hash, a UUID, an opaque identifier), append ` # pragma: allowlist secret` to that exact line and
     re-apply — the pragma silences only the entropy/generic backstop on its line. Anything matching a
     **real named-key format** (AWS `AKIA…`, GCP `AIza…`, Slack/GitHub/OpenAI tokens, PEM blocks) must be
     **REDACTED** instead: the pragma does **not** silence named-key patterns (they are always flagged),
     so pragma-ing one only loops the block — remove the value.

   - **`error:post-commit`** (exit 1, rare) → the post-commit Doctor re-check failed *after* mutating the
     live bundle (normally a concurrent-write race). The JSON carries a `hint`; recover with
     `git checkout -- <bundle-dir>`, then re-run `apply`.
7. **Clean up** the temp file (`rm` it), then surface the outcome as **at most one breadcrumb line** in
   your next user-visible message — `wiki +1: <title>` for a new concept, `wiki ~: <title>` for an update,
   or `wiki blocked (<doctor|secret>): <path>` if the gate blocked it and you could not resolve it. Never a
   prose recap or summary of the concept body — but a block must **always** be surfaced (a silently-
   vanishing capture is the worst failure mode of a persistence tool).

Defer all conformance judgments to the Doctor — if your draft and the Doctor disagree, the Doctor wins.
