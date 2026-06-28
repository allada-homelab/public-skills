from __future__ import annotations
import json
import subprocess
from pathlib import Path
from llm_wiki_optimizer.config import Item
from llm_wiki_optimizer.gold.locate import definitions


def _too_easy(name: str, repo: Path) -> bool:
    # trivially navigable: the bare name appears in <= 1 file (defined, never referenced)
    r = subprocess.run(["grep", "-rwl", name, str(repo)], capture_output=True, text=True)
    return len(r.stdout.split()) <= 1


def build(repo: Path, out: Path, limit: int = 20) -> list[Item]:
    items: list[Item] = []
    for d in definitions(repo):
        name = d.symbol.rsplit(".", 1)[-1]
        if _too_easy(name, repo):
            continue
        items.append(Item(id=f"loc{len(items)}", family="locate", hop=1,
                          question=f"Where is `{name}` defined?", gold=[d]))
        if len(items) >= limit:
            break
    out.write_text(json.dumps([it.model_dump() for it in items], indent=2))
    return items
