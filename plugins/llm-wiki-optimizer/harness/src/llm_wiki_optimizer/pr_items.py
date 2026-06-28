from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Any

from llm_wiki_optimizer.config import GoldLocation, Item

_CUTOFF = "2026-02-01"
_TITLE_PREFIXES = ("feat", "fix", "refactor")
_TITLE_EXCLUDES = ("deps", "bump", "remove", "dead code", "typo", ".py", ".ts", "/")
_SRC_EXCLUDES = ("/tests/", "/test_", "/alembic/versions/", ".gen.", "/__snapshots__/", "conftest.py")


def _is_source_file(path: str) -> bool:
    """True if path looks like a source file (not a test, migration, or generated file)."""
    if not (path.endswith(".py") or path.endswith(".ts")):
        return False
    if not ("/src/" in path or path.count("/") <= 1):
        return False
    return not any(ex in path for ex in _SRC_EXCLUDES)


def _keep_pr(title: str, merged_at: str) -> bool:
    """True if the PR passes date, prefix, and exclusion filters."""
    if merged_at[:10] < _CUTOFF:
        return False
    lower = title.lower()
    if not any(lower.startswith(p) for p in _TITLE_PREFIXES):
        return False
    return not any(ex in lower for ex in _TITLE_EXCLUDES)


def build_pr_items(
    repo_slug: str, out: Path, limit: int = 15, style: str = "change"
) -> list[Item]:
    """Build PR-derived multi-file items for new-developer navigation tasks.

    Fetches the last 200 merged PRs from GitHub, filters by date/title, and
    emits one Item per qualifying PR (3–7 source files, deduplicated file-set).
    Gold = the PR's source files (deterministic, model-free).
    """
    proc = subprocess.run(
        [
            "gh", "pr", "list",
            "-R", repo_slug,
            "--state", "merged",
            "--limit", "200",
            "--json", "number,title,mergedAt,files",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    prs: list[dict[str, Any]] = json.loads(proc.stdout)

    seen_filesets: set[frozenset[str]] = set()
    items: list[Item] = []

    for pr in prs:
        title: str = pr["title"]
        merged_at: str = pr["mergedAt"]
        number: int = pr["number"]

        if not _keep_pr(title, merged_at):
            continue

        src_files = [
            str(f["path"])
            for f in pr["files"]
            if _is_source_file(str(f["path"]))
        ]
        if not (3 <= len(src_files) <= 7):
            continue

        fileset: frozenset[str] = frozenset(src_files)
        if fileset in seen_filesets:
            continue
        seen_filesets.add(fileset)

        if style == "explain":
            question = (
                f'A developer is trying to understand how the work described as "{title}" '
                f"flows through this codebase. "
                f"Which source files are involved? List the repo-relative file paths."
            )
        else:
            question = (
                f'A developer new to this codebase is asked to: "{title}". '
                f"Which source files would they need to read or modify? "
                f"List the repo-relative file paths."
            )

        gold = [
            GoldLocation(file=f, symbol=f, start_line=0, end_line=0)
            for f in src_files
        ]
        items.append(
            Item(
                id=f"pr{number}",
                family="explain",
                hop=len(src_files),
                question=question,
                gold=gold,
            )
        )
        if len(items) >= limit:
            break

    out.write_text(json.dumps([it.model_dump() for it in items], indent=2))
    return items
