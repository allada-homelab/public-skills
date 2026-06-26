#!/usr/bin/env python3
"""Resolve (and persist) the llm-wiki bundle location for a project.

The bundle defaults to `<project-dir>/llm-wiki`, but a project may relocate it by setting a
`bundle_path:` line in a config file under `.claude/` (same shape as `mode.py`). Two layers:

- per-user   — `.claude/llm-wiki.local.md` (git-ignored)  → may name ANY path (self-chosen)
- repo-shared — `.claude/llm-wiki.md` (committed)          → repo-relative + repo-contained ONLY

Per-user overrides repo-shared. A value resolves as: `~`-prefixed → expanduser; absolute → as-is;
else → relative to the project dir. Two safety invariants live HERE (not in init's UI — a hand-edit
or a PR bypasses init entirely):

- PROVENANCE — a value from the *committed* file is honored only if it is repo-relative and resolves
  under the project. `~`/absolute/`..`-escape from the committed file are rejected (fall through). This
  is what makes the committed file safe to trust and the out-of-repo warning sound (every out-of-repo
  bundle is then self-chosen).
- ROOT-COLLAPSE — any value resolving to the project root or an ancestor is rejected: otherwise the
  PreToolUse guard floor's under-bundle check would match every write in the repo.

Anything unset / garbage / rejected → resolver returns None, and the caller falls back to the default,
so an absent config is byte-for-byte identical to today.

Non-goals (documented, mirroring mode.py's minimalism): `$VAR` expansion, inline comments in the value,
Windows drive/UNC paths (POSIX only). Use `~` or an absolute path; don't hand-write comments.

Usage:
  bundle_path.py resolve [project-dir]            print the EFFECTIVE bundle root (configured or default)
  bundle_path.py set <value> [project-dir] [--shared]
                                                  write/update bundle_path: in the per-user (or, with
                                                  --shared, the committed) config; refuses an unsafe value
"""
import os
import re
import sys

_BP_RE = re.compile(r"(?mi)^[ \t]*bundle_path[ \t]*:[ \t]*(.+?)[ \t]*$")


def _read_bundle_path(config_file):
    """Return a stripped bundle_path: value from one config file, or None.

    No $VAR expansion, no inline-comment stripping (documented non-goals)."""
    try:
        with open(config_file, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None  # absent / unreadable file
    m = _BP_RE.search(text)
    value = m.group(1).strip() if m else ""
    return value or None  # no line / empty → None


def _resolve_one(value, source, project_dir):
    """Resolve + validate ONE layer's value. None ⇒ this layer yields nothing (fall through).

    `source` is "local" (self-chosen: .local.md / --bundle) or "shared" (committed .md).
    `project_dir` must already be absolute.
    """
    if not value:
        return None
    if value.startswith("~"):  # MUST precede isabs: ~/x is not absolute
        if source == "shared":
            return None  # PROVENANCE: a committed value may not point off-repo
        resolved = os.path.expanduser(value)
        if resolved.startswith("~"):
            return None  # HOME unset, ~ unexpanded → garbage → fail safe
    elif os.path.isabs(value):
        if source == "shared":
            return None  # PROVENANCE: committed value → repo-relative only
        resolved = value
    else:
        resolved = os.path.join(project_dir, value)  # repo-relative
    resolved = os.path.normpath(resolved)  # logical path only — NO realpath here
    try:
        # ROOT-COLLAPSE (all sources): bundle must not BE or CONTAIN the project root, else the
        # guard floor's under-bundle check matches every write in the repo.
        if os.path.commonpath([resolved, project_dir]) == resolved:
            return None
        # PROVENANCE containment (shared only): a committed value must stay inside the repo.
        if source == "shared" and os.path.commonpath([resolved, project_dir]) != project_dir:
            return None
    except ValueError:
        return None  # mixed abs/rel or different Windows drives → fail safe
    return resolved


def resolve_configured_bundle(project_dir):
    """Return the configured bundle path, or None when unset/garbage/rejected (→ caller's default).

    Precedence: per-user .local.md overrides repo-shared .claude/llm-wiki.md. A rejected layer
    falls through to the next, then to the caller's default.
    """
    project_dir = os.path.abspath(project_dir)  # commonpath needs an absolute base
    cdir = os.path.join(project_dir, ".claude")
    for fname, source in (("llm-wiki.local.md", "local"), ("llm-wiki.md", "shared")):
        resolved = _resolve_one(_read_bundle_path(os.path.join(cdir, fname)), source, project_dir)
        if resolved:
            return resolved
    return None


def bundle_root(project_dir):
    """The EFFECTIVE bundle root: the configured path, or the default `<project>/llm-wiki`.

    The default keeps `project_dir` raw (un-abspath'd) so it is byte-for-byte identical to the
    pre-feature literal; callers that need symlink resolution apply realpath themselves."""
    return resolve_configured_bundle(project_dir) or os.path.join(project_dir, "llm-wiki")


# ---- config writer (used by /llm-wiki:init) --------------------------------------------------

def set_bundle_path(value, project_dir, shared=False):
    """Write/update the `bundle_path:` line in the per-user (or, if shared, committed) config.

    Refuses an unsafe value (root-collapse always; non-repo-relative/non-contained when shared) —
    same invariants as the resolver, so the writer never *helps* create one. Returns the config
    path written. Raises ValueError on a refused value.
    """
    abs_project = os.path.abspath(project_dir)
    if _resolve_one(value, "shared" if shared else "local", abs_project) is None:
        raise ValueError(
            "refusing to set bundle_path=%r: %s" % (
                value,
                "a committed (shared) value must be a repo-relative path inside the project"
                if shared else
                "value resolves to the project root or an ancestor (would collapse the guard scope)",
            )
        )
    cdir = os.path.join(project_dir, ".claude")
    os.makedirs(cdir, exist_ok=True)
    path = os.path.join(cdir, "llm-wiki.md" if shared else "llm-wiki.local.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    new_line = "bundle_path: %s" % value
    if _BP_RE.search(text):
        text = _BP_RE.sub(new_line, text, count=1)  # update in place, preserving mode: etc.
    elif text.startswith("---"):
        # insert into the existing frontmatter block (after the opening ---)
        text = re.sub(r"\A---[ \t]*\n", "---\n%s\n" % new_line, text, count=1)
    else:
        text = "---\n%s\n---\n%s" % (new_line, text)  # create frontmatter
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main(argv):
    if not argv:
        print("usage: bundle_path.py {resolve|set} ...", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "resolve":
        project = argv[1] if len(argv) > 1 else (os.environ.get("CLAUDE_PROJECT_DIR") or ".")
        print(bundle_root(project))
        return 0
    if cmd == "set":
        rest = [a for a in argv[1:] if a != "--shared"]
        shared = "--shared" in argv[1:]
        if not rest:
            print("usage: bundle_path.py set <value> [project-dir] [--shared]", file=sys.stderr)
            return 2
        value = rest[0]
        project = rest[1] if len(rest) > 1 else (os.environ.get("CLAUDE_PROJECT_DIR") or ".")
        try:
            written = set_bundle_path(value, project, shared=shared)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(written)
        return 0
    print("unknown subcommand: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
