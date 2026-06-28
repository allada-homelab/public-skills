from pathlib import Path
from llm_wiki_optimizer.config import CellKey, CellResult
from llm_wiki_optimizer.store import CellStore


def _key(seed: int = 0) -> CellKey:
    return CellKey(item_id="i1", candidate_id="c1", sut="sonnet", condition="with_wiki", seed=seed)


def test_put_then_get_roundtrips(tmp_path: Path):
    s = CellStore(tmp_path / "run.db")
    s.put(_key(), CellResult(predicted=["a.b"], calls=2))
    got = s.get(_key())
    assert got is not None and got.predicted == ["a.b"] and got.calls == 2


def test_missing_cell_returns_none(tmp_path: Path):
    s = CellStore(tmp_path / "run.db")
    assert s.get(_key(seed=9)) is None


def test_put_is_idempotent_upsert(tmp_path: Path):
    s = CellStore(tmp_path / "run.db")
    s.put(_key(), CellResult(predicted=["x"]))
    s.put(_key(), CellResult(predicted=["y"]))  # re-run overwrites same cell
    assert s.get(_key()).predicted == ["y"]


def test_pending_filters_done_cells(tmp_path: Path):
    s = CellStore(tmp_path / "run.db")
    all_keys = [_key(0), _key(1), _key(2)]
    s.put(_key(1), CellResult(predicted=["done"]))
    pending = s.pending(all_keys)
    assert pending == [_key(0), _key(2)]  # resume = compute only empty cells


def test_reopen_persists(tmp_path: Path):
    db = tmp_path / "run.db"
    CellStore(db).put(_key(), CellResult(predicted=["persisted"]))
    assert CellStore(db).get(_key()).predicted == ["persisted"]
