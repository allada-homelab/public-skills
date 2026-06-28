from __future__ import annotations
import sqlite3
from pathlib import Path
from llm_wiki_optimizer.config import CellKey, CellResult

_COLS = ("item_id", "candidate_id", "sut", "condition", "seed")


class CellStore:
    """Cell-level checkpoint store. Resume = compute only the empty cells."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cells ("
            "item_id TEXT, candidate_id TEXT, sut TEXT, condition TEXT, seed INTEGER,"
            "result TEXT NOT NULL,"
            "PRIMARY KEY (item_id, candidate_id, sut, condition, seed))"
        )
        self._db.commit()

    def put(self, key: CellKey, result: CellResult) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cells "
            "(item_id, candidate_id, sut, condition, seed, result) VALUES (?,?,?,?,?,?)",
            (key.item_id, key.candidate_id, key.sut, key.condition, key.seed,
             result.model_dump_json()),
        )
        self._db.commit()

    def get(self, key: CellKey) -> CellResult | None:
        row = self._db.execute(
            "SELECT result FROM cells WHERE item_id=? AND candidate_id=? AND sut=? "
            "AND condition=? AND seed=?",
            (key.item_id, key.candidate_id, key.sut, key.condition, key.seed),
        ).fetchone()
        return None if row is None else CellResult.model_validate_json(row[0])

    def pending(self, keys: list[CellKey]) -> list[CellKey]:
        return [k for k in keys if self.get(k) is None]
