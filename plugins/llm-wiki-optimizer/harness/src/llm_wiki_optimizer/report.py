from __future__ import annotations
import json
import statistics
from pathlib import Path
from typing import Any
from llm_wiki_optimizer.config import Item
from llm_wiki_optimizer.score import prf1, uplift


def _f1(cell: dict[str, Any], gold: list[str]) -> float:
    if not cell.get("ok", False):
        return 0.0
    return prf1(cell["predicted"], gold)[2]


def report(items_path: Path, cells_path: Path) -> dict[str, Any]:
    items = {d["id"]: Item.model_validate(d) for d in json.loads(items_path.read_text())}
    cells = json.loads(cells_path.read_text())["cells"]
    idx = {(c["item_id"], c["candidate_id"], c["sut"], c["condition"]): c for c in cells}
    cand_ids = sorted({c["candidate_id"] for c in cells})

    def f1(item_id: str, cand: str, sut: str, cond: str) -> float:
        c = idx.get((item_id, cand, sut, cond))
        return 0.0 if c is None else _f1(c, [g.symbol for g in items[item_id].gold])

    real = [c for c in cand_ids if c != "__baseline__"]
    out: dict[str, Any] = {}
    # (1) detectable uplift per SUT: best candidate's with-wiki F1 minus the FIXED ablated baseline
    for sut in ("sonnet", "opus"):
        ups = [uplift(max(f1(i, c, sut, "with_wiki") for c in real),
                      f1(i, "__baseline__", sut, "ablated")) for i in items]
        out[f"mean_uplift_{sut}"] = round(statistics.mean(ups), 4) if ups else 0.0
    # (2) cross-SUT candidate-ranking correlation (with_wiki mean F1 per candidate)
    for sut in ("sonnet", "opus"):
        out[f"candidate_scores_{sut}"] = [
            round(statistics.mean(f1(i, c, sut, "with_wiki") for i in items), 4) for c in real]
    out["candidates"] = real
    out["ranking_note"] = "compare candidate_scores_sonnet vs _opus orderings; disagreement invalidates cheap-search/expensive-gate"
    return out
