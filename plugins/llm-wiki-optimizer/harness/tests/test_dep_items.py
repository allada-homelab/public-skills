from __future__ import annotations
from pathlib import Path

from llm_wiki_optimizer.dep_items import importers

FIX = Path(__file__).parent / "fixtures" / "minirepo"


def test_importers_from_form() -> None:
    """from pkg.mod import alpha -> consumer.py is returned as an importer."""
    result = importers(FIX, "pkg.mod")
    assert result == ["pkg/consumer.py"]


def test_importers_import_form(tmp_path: Path) -> None:
    """`import pkg.mod` -> the file is returned as an importer."""
    (tmp_path / "user.py").write_text("import pkg.mod\n")
    result = importers(tmp_path, "pkg.mod")
    assert result == ["user.py"]
