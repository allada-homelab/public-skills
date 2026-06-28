import pytest
from pydantic import ValidationError
from llm_wiki_optimizer.config import GoldLocation, Item, CellKey, CellResult


def test_gold_location_normalizes_symbol():
    g = GoldLocation(file="pkg/mod.py", symbol="pkg.mod.func", start_line=10, end_line=20)
    assert g.file == "pkg/mod.py"
    assert g.symbol == "pkg.mod.func"


def test_item_requires_nonempty_gold():
    with pytest.raises(ValidationError):
        Item(id="i1", family="locate", hop=1, question="where?", gold=[])


def test_cellkey_is_hashable_and_stable():
    k1 = CellKey(item_id="i1", candidate_id="c1", sut="sonnet", condition="with_wiki", seed=0)
    k2 = CellKey(item_id="i1", candidate_id="c1", sut="sonnet", condition="with_wiki", seed=0)
    assert k1 == k2 and hash(k1) == hash(k2)


def test_cellresult_carries_locations_and_cost():
    r = CellResult(predicted=["pkg.mod.func"], calls=3, ok=True, error=None)
    assert r.predicted == ["pkg.mod.func"]
    assert r.calls == 3
