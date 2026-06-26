# Tech plan — configurable bundle location

**Status:** planned (not yet implemented)
**Goal:** let a project point llm-wiki at a bundle location other than the hardcoded
`${CLAUDE_PROJECT_DIR}/llm-wiki` — e.g. repo-relative `.agent-context/`, or a home/absolute
path like `~/new-wiki` — and have that choice **persist across chat sessions**.

## Decisions (locked)

1. **Storage: two layers, chosen at `init` time.** The bundle location can be either:
   - **per-user** — `.claude/llm-wiki.local.md` (git-ignored, `.gitignore:5`; the file `mode.py` already
     reads), or
   - **repo-shared** — `.claude/llm-wiki.md` (committed; every teammate who clones inherits it).

   `init` asks which (see "`init` is interactive"). The resolver reads **both**, with **per-user
   overriding repo-shared** (local beats shared beats default) — standard override semantics. Only
   `bundle_path` is layered; `mode` stays per-user-only in `.local.md` (don't widen its scope here).
   **Constraint (resolver-enforced, not just UI):** a `~`/absolute/`..`-escape path is machine-specific
   and is meaningless — and unsafe — in a committed file (a teammate's guards and auto-writes would follow
   it). The resolver honors a committed value only if it is repo-relative *and* repo-contained (see
   "provenance" in the resolver section); `init` correspondingly offers the shared option only for a
   repo-relative path. The UI rule is convenience; the resolver invariant is the control.
2. **Out-of-repo bundles: warn, don't block.** If the resolved bundle is not under a git work tree,
   emit a loud warning (auto-mode writes are not reversible) but proceed. Setting `bundle_path` to an
   external path is itself the opt-in.

## Mechanism rationale (why this shape)

- **Hooks have no args.** `hooks.json` invokes every hook with no CLI arguments — hooks read only env
  + stdin JSON. So `--bundle` *cannot* reach the 6 hooks or the 2 guards. A config-file-backed resolver
  is their **only** relocation channel. This is why persistent relocation must go through `bundle_path:`,
  not `--bundle`.
- **Mirror `mode.py` exactly.** Stdlib-only (no YAML dep), regex on a single line, fail-safe default.
  The project is stdlib-only by constraint.

## The resolver — `scripts/bundle_path.py` (new)

Importable function **and** a CLI `main` (commands are markdown and shell out; scripts import).

```python
_BP_RE = re.compile(r"(?mi)^[ \t]*bundle_path[ \t]*:[ \t]*(.+?)[ \t]*$")

def _read_bundle_path(config_file):
    """Return a stripped bundle_path: value from one config file, or None.

    No $VAR expansion, no inline-comment stripping (non-goals — see "Non-goals").
    """
    try:
        with open(config_file, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None                       # absent file
    m = _BP_RE.search(text)
    value = m.group(1).strip() if m else ""
    return value or None                  # no line / empty → None

def _resolve_one(value, source, project_dir):
    """Resolve+validate ONE layer's value. None ⇒ this layer yields nothing (fall through).

    `source` is "local" (self-chosen: .local.md / --bundle) or "shared" (committed .md).
    """
    if not value:
        return None
    if value.startswith("~"):             # MUST precede isabs: ~/x is not absolute
        if source == "shared":
            return None                   # PROVENANCE: committed file may not point off-repo
        resolved = os.path.expanduser(value)
        if resolved.startswith("~"):
            return None                   # HOME unset, ~ unexpanded → garbage → fail safe
    elif os.path.isabs(value):
        if source == "shared":
            return None                   # PROVENANCE: committed file → repo-relative only
        resolved = value
    else:
        resolved = os.path.join(project_dir, value)   # repo-relative
    resolved = os.path.normpath(resolved)             # logical path only — NO realpath here
    # ROOT-COLLAPSE guard (all sources): bundle must not BE or CONTAIN the project root,
    # else the PreToolUse floor's `_under` matches every write in the repo.
    if os.path.commonpath([resolved, project_dir]) == resolved:
        return None
    # PROVENANCE containment (shared only): a committed value must stay inside the repo.
    if source == "shared" and os.path.commonpath([resolved, project_dir]) != project_dir:
        return None
    return resolved

def resolve_configured_bundle(project_dir):
    """Return the configured bundle path, or None when unset/garbage/rejected (→ caller's default).

    Precedence: per-user .local.md overrides repo-shared .claude/llm-wiki.md. A rejected
    layer falls through to the next, then to the caller's default.
    """
    project_dir = os.path.abspath(project_dir)        # commonpath needs an absolute base
    cdir = os.path.join(project_dir, ".claude")
    for fname, source in (("llm-wiki.local.md", "local"), ("llm-wiki.md", "shared")):
        resolved = _resolve_one(_read_bundle_path(os.path.join(cdir, fname)), source, project_dir)
        if resolved:
            return resolved
    return None
```

> `commonpath` raises `ValueError` on mixed abs/rel or different Windows drives — `abspath` handles the
> former; the latter is a documented non-goal (POSIX only). Wrap in `try/except ValueError: return None`
> as a belt-and-suspenders fail-safe.

**Keystone:** returning **`None` when unset** (never the default). Every call site keeps its own
"no config" behavior, so absent config is byte-for-byte identical to today.

**Two safety invariants live in the resolver, not in init's UI** (a hand-edited or PR'd config bypasses
init entirely — review found this is the actual threat surface):
- **Provenance** — a value from the *committed* `.claude/llm-wiki.md` is honored only if it is
  repo-relative *and* resolves under the project (`~`, absolute, and `..`-escape are rejected and fall
  through). `~`/absolute are allowed only from the self-chosen `.local.md` / `--bundle`. This is what makes
  the committed file safe to trust and Decision 2's warn-don't-block sound (every out-of-repo bundle is
  then self-chosen). Decision 1's "shared ⇒ repo-relative" thus becomes a *resolver invariant*, with the
  init prompt as mere convenience.
- **Root-collapse** — any value that resolves to the project root or an ancestor is rejected (verified:
  `.`, `./`, empty, `..`, `/`, absolute ancestors all collapse the guard scope onto the whole repo). Same
  rejection in the `set` writer so a hand-edit can't persist one silently.

- Hooks/guards: `resolve_configured_bundle(pd) or os.path.join(pd, "llm-wiki")`
- Commands: `--bundle` arg → `resolve_configured_bundle(pd)` → [today's default-or-walk-up]

`project_dir` is a **parameter**, supplied by the caller as
`os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()` — identical to the guards
today, so an unset project dir still anchors to cwd.

## Precedence

- **Commands:** `--bundle` arg > config `bundle_path` > walk-up-for-root-`index.md` > default `./llm-wiki`.
- **Hooks/guards:** config `bundle_path` > default `./llm-wiki` (no `--bundle`, no walk-up).

`--bundle`/`bundle_path` are *stated intent*; walk-up is *discovery* (runs only when neither is present),
so they cannot fight. `--bundle` beats config because it's the most-local, per-invocation override.

## Security — both guards MUST use the resolver

`secret_guard.py` (~L29-32) and `doctor_guard.py` (~L38-40) each independently compute
`realpath(join(project, "llm-wiki"))` and scope their PreToolUse deny via `commonpath`/`_under`. If the
bundle relocates but a guard keeps the old literal, `_under(target, old_root)` is False for every write
to the **real** bundle → guard fails open → secret + non-conformant writes to the relocated bundle are
**silently no longer denied**. The auto-mode safety floor disappears with zero signal.

Both guards replace their literal with:

```python
project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
bundle = os.path.realpath(resolve_configured_bundle(project) or os.path.join(project, "llm-wiki"))
```

**Symlink interaction (load-bearing):** the resolver returns the *logical* path (no realpath); each
guard keeps wrapping it in `os.path.realpath` for **both** root and target, as today. `commonpath` is
purely lexical, so root and target must be normalized identically or the check mismatches and fails
open. Keeping realpath guard-side means `~/wiki`, repo-relative, and absolute all behave identically,
and the existing trick (realpath leaves a non-existent tail intact for not-yet-created files) is preserved.

## Out-of-repo warning (decision 2)

The real safety property is "under *some* git work tree," not "in *this* repo." A `~/new-wiki` the user
`git init`-ed keeps full reversibility; an absolute path under no repo does not.

**Owner: `hook_session_start.py` only** (fires exactly once per session, already resolves `project_dir`,
already has the `additionalContext` channel). The "first write of a session" leg is **dropped** — it
would need a new stateful marker or a check in every write command for no benefit, since SessionStart
already warned before any write.

**Check:** run on `os.path.realpath(<resolved-bundle>)` (match the guards' realpath treatment, so a
symlink under the repo pointing outside it can't masquerade as in-repo): `git -C <realpath> rev-parse
--show-toplevel` succeeds **and** the bundle is under that toplevel.
- git-backed (even a different repo) → proceed silently.
- not git-backed → warn loudly: *"bundle at `<path>` is not under a git work tree — auto-mode writes are
  not reversible; run `git init` there or switch to `mode: curated`."*

Note: provenance already forces a *shared*-sourced bundle repo-contained, so only a self-chosen
(`.local.md`/`--bundle`) bundle can ever trip this warning.

## Display literals are call sites too

`hook_session_start.py` (~L87, L89) hardcodes `llm-wiki/index.md` in the **preload text** Claude reads.
Derive it from the resolved path (e.g. `os.path.relpath(index_path, project_dir)`), or a relocated
bundle prints wrong paths in its own preload. Byte-for-byte compat for the default holds only because
the derived value equals `llm-wiki` when unset — it does *not* hold if the literal is left in place.

## `init` is interactive and *writes* the config

`init` is the one command that both **resolves** and **establishes** the location, which dissolves the
chicken-and-egg (otherwise the user must hand-edit `.claude/llm-wiki.local.md` before the first init).

Resolution order for `init`'s creation target:
1. Positional arg / `--bundle <path>` → use it (explicit, one-off).
2. Configured `bundle_path` (if already set) → use it silently.
3. **Otherwise ask the user** (via `AskUserQuestion`) — at most **two prompts**:
   - **(a) Location**, offering: `llm-wiki/` **(Recommended)**, the default; `.agent-context/` (a named
     shortcut for the common repo-relative case); *Other* → free-text (accepts repo-relative, `~/…`, or
     absolute).
   - **(b) Tracking** — a single 4-option question that folds scope + ignore-strategy into one (each option
     maps to a fixed storage outcome). Asked only when (a) is **non-default** *and* **repo-relative**:

     | Option | Config file | Ignore action |
     |--------|-------------|---------------|
     | Shared with team | committed `.claude/llm-wiki.md` (+ `git add` reminder) | none — bundle is committed too |
     | **Just me, keep out of the shared repo (Recommended)** | `.local.md` | append to `.git/info/exclude` |
     | Each person keeps their own here | `.local.md` | append to committed `.gitignore` |
     | Just my config; I'll commit the concepts | `.local.md` | none (track concepts) |

     The exclude/`.gitignore` write is an **idempotent append** (skip if already present), via
     `git rev-parse --git-path info/exclude` (worktree/submodule-correct). This ignores the *concepts* and
     is distinct from the always-on `.llm-wiki/` state-dir ignore.

     **Skip (b) entirely when the path is `~`/absolute** — force single-user (`.local.md`), no ignore action
     (an out-of-repo bundle isn't tracked by this repo, and a machine-specific path can't be shared); say why.

**Persisting the choice.** When the resolved target is **non-default**, `init` writes
`bundle_path: <value>` into the file the scope prompt selected, so every later session, command, and
hook/guard resolves to it automatically — the user never edits the dotfile by hand. A choice of the
default `llm-wiki/` writes nothing (preserving the "absent config → default" invariant). This needs a
small deterministic writer — extend the resolver module with `bundle_path.py set <value> [project-dir]
[--shared]` that adds/updates the single `bundle_path:` line in the target file's frontmatter (`.local.md`
by default, `.claude/llm-wiki.md` with `--shared`), **creating the file/frontmatter if absent and
preserving any existing `mode:` line** (don't LLM-edit YAML — it drifts). `set` **refuses** a
root-collapse value (`.`/`..`/`/`/ancestor) and a `--shared` value that isn't repo-relative + repo-contained
(same invariants as the resolver). If scope is repo-shared, `init` also reminds the user to
`git add .claude/llm-wiki.md` (a committed file only shares once tracked).

**Keep the shared reader scoped to `bundle_path` alone.** `mode.py` reads only `.local.md` (mode stays
per-user). The new two-file reader must never be generalized into a "read shared config" helper that
could surface `mode:` from the committed file — a committed file flipping a teammate `curated`→`proactive`
would silently disarm the confirm-gate. Add a fixture asserting `mode:` in `.claude/llm-wiki.md` is ignored.

**Asking is input-gathering, not a write-approval prompt** — so `init` asks even in an auto mode when
the location is unspecified (creating a bundle in the wrong place is awkward to undo). It does **not**
ask when the arg or config already names a location.

After establishing the target, the existing init flow is unchanged: stage → Doctor-gate → create. And
read/write commands still stop with "Run `/llm-wiki:init` first" when the *configured* location holds no
bundle yet — `init` is what creates it there. **Two existing-init literals must now name the resolved
path:** the refuse message ("A bundle already exists here …" → "… at `<resolved>`") and the
"Run `/llm-wiki:init` first" stop, since the location is no longer fixed.

**Re-init discoverability.** When config already names a location (resolution step 2, silent-use), print
one line: *"llm-wiki configured to `<resolved>`; pass a path (e.g. `/llm-wiki:init .agent-context`) to
change it."* — so relocating is discoverable without hand-editing the dotfile.

## Relocation is not (yet) a migration — detect, don't orphan

The single most likely reason to want a configurable location is *"I have a wiki and want to move it."*
Yet init globs only the **new** target for `index.md` — so pointing at a new location while a bundle
already exists at the old one would create a fresh empty bundle and **silently orphan** the old concepts,
with config + hooks + guards all following the empty new path. That is the one path the flow must not take.

**Floor (this feature):** before writing config / creating at a non-default target, glob the
**previously-resolved** location (current config value, else `./llm-wiki`) for a root `index.md`. If one
exists and old ≠ new, **stop** and offer **Move / Keep-both / Cancel** (default **Cancel** — safe):
- *Cancel* → write nothing, create nothing.
- *Keep-both* → proceed, but warn loudly naming **both** paths (old bundle stays put, unmanaged).
- *Move* → a true bundle-**root** move. `reorganize` moves *within* a bundle, not the root, so this is
  **new machinery** — **deferred to a follow-up**; until then *Move* falls back to *Keep-both* + a pointer.

Never silently orphan. Add a fixture: existing bundle at default + init to a new path → assert
refuse-or-confirm, not a silent create.

## Non-goals (documented, so they aren't mistaken for oversights)

- **`$VAR` expansion** — `bundle_path: $HOME/x` is a literal `$HOME` dir (verified). Use `~` or an
  absolute path. (Mirrors `mode.py`'s minimalism.)
- **Windows / drive-letter / UNC paths** — POSIX only (the feature leans on `git rev-parse`,
  `.git/info/exclude`, realpath semantics). A cross-drive target makes `_under` raise→`False` (fails open
  for that write), which is correct: a cross-drive path genuinely isn't under the bundle.
- **Two bundles in one repo** — one configured bundle per project; a single `bundle_path:` scalar can't
  express two. Use `--bundle` per-invocation for a one-off second bundle.
- **Inline comments** in the value — the `(.+?)$` capture would swallow `# comment` into the path. The
  value is writer-generated; don't add a comment-stripper, just don't hand-write comments.

## `.gitignore` follow-up

`.gitignore:8` ignores the state dir by literal path `llm-wiki/.llm-wiki/`. The `.llm-wiki/` markers
live *inside* the bundle, so they relocate automatically with `bundle_path` — but the gitignore pattern
won't match the new location. Generalize it to `**/.llm-wiki/` (or document that relocating requires a
matching gitignore edit). Note the asymmetry of the two config files: `.claude/llm-wiki.local.md` **must
stay git-ignored** (`.gitignore:5`, per-user) while `.claude/llm-wiki.md` **must stay tracked** (committed,
repo-shared) — the exact-path ignore on line 5 already leaves `.md` un-ignored, so no change needed there,
but don't broaden it to a glob that catches both.

## Full call-site change list (locators, not contracts — verify on touch)

**New:** `scripts/bundle_path.py` — `resolve_configured_bundle()` (reads `.local.md` then committed
`.claude/llm-wiki.md`, local wins) + CLI, **plus a `set <value> [project-dir] [--shared]` subcommand**
that writes/updates the `bundle_path:` line in `.local.md` (or `.claude/llm-wiki.md` with `--shared`),
creating file/frontmatter if absent and preserving `mode:`.

**Guards (security-critical):**
- `secret_guard.py` ~L29-32 — resolver + realpath
- `doctor_guard.py` ~L38-40 — resolver + realpath

**Hooks:**
- `hook_session_start.py` ~L64,73 (bundle dir) + ~L87,89 (derive display literals)
- `hook_session_end.py` ~L46,50 (`log.md` path)
- `hook_post_tool.py` ~L33,55,58 (capture-pending marker, index check, `_under`)
- `hook_stop.py` ~L48,59,64 (index check, capture-pending marker)
- `hook_user_prompt.py` ~L32,41,43 (index check, last-session marker)

**Commands (10):** update the resolution preamble in
`capture/explore/query/prune/tend/conform/init/refine/reorganize/ingest .md` to read
`bundle_path` (shell out to `bundle_path.py`) between the `--bundle` arg and the existing default.
`init.md` gets extra logic: `AskUserQuestion` location prompt + the single 4-option tracking prompt
(repo-relative non-default only); relocation detect (Move/Keep-both/Cancel); a `bundle_path.py set
[--shared]` call to persist a non-default choice; an idempotent append to `.git/info/exclude` or
`.gitignore` for the personal-ignore case; and path-naming in the refuse/stop literals (see "`init` is
interactive").
- *Transitive, no independent edit:* `explore.md`, `query.md`, `tend.md` each reference
  `<bundle-root>/.llm-wiki/consultations.json` via the resolved bundle-root variable — these relocate
  automatically once the resolution preamble feeds that variable; **verify the variable flows through**,
  don't treat them as separate literals.

**Test harness:** `scripts/hook_fixtures/run_hooks.sh` currently hardcodes `CLAUDE_PROJECT_DIR="$tmp"` with
no per-case override — matrix cases needing a controlled `HOME` or an *unset* `CLAUDE_PROJECT_DIR` (the
home-relative, unset-project, and HOME-unset cases) **cannot be expressed** without extending it. Add a
per-case `env` slot (source an optional `env` file in the fixture dir / run under `env -i`). **Lands with
the fixtures, not after.**

**Docs:** `phase-3-autonomy-architecture.md` (qualify the "git-reversible" claim per decision 2);
`CLAUDE.md` (default-location note, **the `scripts/` inventory line + Architecture & conventions section
both need `bundle_path.py` added**, and the new hook-fixture count); `.gitignore:8` (generalize state-dir
pattern); **`llm-wiki/guard-bundle-path-coupling.md`** (the dogfood concept describing this exact gotcha —
once shipped, update its "What works" to name `bundle_path.py` as the shared resolver and add a Related
link to a configurable-bundle-location concept, so it reads as resolved, not open).

**Untouched (confirmed clean):** `SKILL.md`, all `skills/wiki/references/*`, `agents/wiki-explorer.md` —
zero path literals.

## Test matrix — add fixtures FIRST (TDD, per CLAUDE.md)

Extend the `hook_fixtures` corpus (currently `pass=31`). Each case sets/unsets `CLAUDE_PROJECT_DIR`,
optionally writes `.claude/llm-wiki.local.md` with a `bundle_path:` line, feeds a PreToolUse event on
stdin, asserts resolved root / deny decision.

| # | Case | Setup | Assert |
|---|------|-------|--------|
| 1 | **absent → default** (regression) | no config | resolver→None; root == `${PD}/llm-wiki` |
| 2 | repo-relative | `bundle_path: .agent-context` | root == `${PD}/.agent-context` |
| 3 | home-relative | `bundle_path: ~/new-wiki` + HOME set | root == `${HOME}/new-wiki` |
| 4 | absolute | `bundle_path: /srv/shared/wiki` | root == `/srv/shared/wiki` |
| 5 | garbage → default | empty/malformed line | resolver→None; root == default |
| 6 | `CLAUDE_PROJECT_DIR` unset → cwd | unset env, no config | root == `${cwd}/llm-wiki` |
| 7 | `~` unexpanded (HOME unset) → default | `bundle_path: ~/x`, no HOME | resolver→None; root == default |
| 8 | symlinked bundle still caught | relocate + symlink dir; write through symlink | deny |
| 9 | **SECURITY: relocate, secret write to NEW location** | config relocates; secret in Write to new path | **deny** |
| 10 | **SECURITY: garbage config, secret write to default** | malformed config; secret write to `./llm-wiki` | **deny** |
| 11 | out-of-repo → warning emitted | absolute path under no git work tree | warning present |
| 12 | repo-shared only | `bundle_path:` in `.claude/llm-wiki.md`, no `.local.md` | root == shared value |
| 13 | **local overrides shared** | `bundle_path: A` in `.local.md` + `bundle_path: B` in `.md` | root == A |
| 14 | shared garbage falls through | malformed `.md`, no `.local.md` | resolver→None; root == default |
| 15 | local garbage → valid shared | malformed `.local.md` + valid `bundle_path: B` in `.md` | root == B |
| 16 | **SEC/provenance: shared `..`-escape** | `bundle_path: ../../etc` in `.md`, no `.local.md` | resolver→None; root == default (**not** `/etc`) |
| 17 | **SEC/provenance: shared `~`/abs** | `bundle_path: ~/x` or `/srv/x` in `.md` | resolver→None; root == default |
| 18 | **provenance: same value in local IS honored** | the case-16/17 value in `.local.md` | root == that path (proves the distinction is *source*, not form) |
| 19 | **SEC/root-collapse** | `bundle_path: .` (also test `..`, `/`) any source | resolver→None; root == default (floor not repo-wide) |
| 20 | mode not surfaced from shared | `mode: curated` in `.claude/llm-wiki.md`, none in `.local.md` | mode resolves `proactive` (shared `mode:` ignored) |

Highest-value: **9 + 10** (guard tracks config; fail-safe keeps the floor) and **16–19** (the adversarial
provenance + root-collapse cases — they must **fail against the plan-as-first-drafted** and pass only once
the resolver invariants land; that's the TDD point). Plus a relocation fixture (existing bundle at default
+ init to a new path → assert refuse-or-confirm, not silent create).

After implementing: re-run all three corpora (`fixtures` → 24/0, `ops_fixtures` → 19/0, `hook_fixtures`
→ 31 + new). Record the new hook-fixture count in `CLAUDE.md`.

## Risks / the claim most likely wrong

- Line numbers above are grep/Read snapshots and will drift during implementation — treat as locators.
  The call-site **shapes** (`os.path.join(project, "llm-wiki")` and the display-string literals) are
  confirmed and are what to match on.
- `--bundle` divergence foot-gun: a user who relocates via `--bundle` only (no config) gets commands
  writing to the new path while hooks/guards still watch the default. Recommend commands warn when
  `--bundle` diverges from the resolved/configured path.
- Orphaned state markers after relocation (cosmetic, self-healing): the old `.llm-wiki/` state dir
  (`last-session`, `capture-pending`) is left behind, so the once-per-session consult nudge re-fires once
  in the first session after a move. No action needed — it heals after one session; noted so it isn't
  mis-reported as a bug.
