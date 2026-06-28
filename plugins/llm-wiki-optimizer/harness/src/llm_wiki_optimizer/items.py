from __future__ import annotations
import json
import subprocess
from pathlib import Path
from llm_wiki_optimizer.config import GoldLocation, Item
from llm_wiki_optimizer.gold.locate import definitions


def _too_easy(name: str, repo: Path) -> bool:
    # trivially navigable: the bare name appears in <= 1 file (defined, never referenced)
    r = subprocess.run(["grep", "-rwl", name, str(repo)], capture_output=True, text=True)
    return len(r.stdout.split()) <= 1


def build(repo: Path, out: Path, limit: int = 20) -> list[Item]:
    defs = list(definitions(repo))
    # a name defined in >1 file makes "where is <name> defined?" ambiguous (e.g. Alembic `upgrade`)
    name_files: dict[str, set[str]] = {}
    for d in defs:
        name_files.setdefault(d.symbol.rsplit(".", 1)[-1], set()).add(d.file)

    # one unambiguous public def per file, then stride-sample across files for breadth across the repo
    per_file: dict[str, GoldLocation] = {}
    for d in defs:
        name = d.symbol.rsplit(".", 1)[-1]
        if name.startswith("_") or d.file in per_file or len(name_files[name]) > 1:
            continue
        per_file[d.file] = d
    files = sorted(per_file)
    step = max(1, len(files) // (limit * 2)) if files else 1

    picked: list[GoldLocation] = []
    for f in files[::step]:
        d = per_file[f]
        if _too_easy(d.symbol.rsplit(".", 1)[-1], repo):
            continue
        picked.append(d)
        if len(picked) >= limit:
            break

    items = [
        Item(id=f"loc{i}", family="locate", hop=1,
             question=f"Where is `{d.symbol.rsplit('.', 1)[-1]}` defined?", gold=[d])
        for i, d in enumerate(picked)
    ]
    out.write_text(json.dumps([it.model_dump() for it in items], indent=2))
    return items
