from pathlib import Path
from llm_wiki_optimizer.gold.locate import definitions

FIX = Path(__file__).parent / "fixtures" / "minirepo"


def test_extracts_function_and_method_defs():
    defs = definitions(FIX)
    by_symbol = {d.symbol: d for d in defs}
    assert "pkg.mod.alpha" in by_symbol
    assert by_symbol["pkg.mod.alpha"].file == "pkg/mod.py"
    assert by_symbol["pkg.mod.alpha"].start_line == 1
    assert "pkg.mod.Beta" in by_symbol
    assert "pkg.mod.Beta.gamma" in by_symbol


def test_symbol_is_dotted_and_repo_relative():
    defs = definitions(FIX)
    assert all(not d.file.startswith("/") for d in defs)   # repo-relative paths
    assert all("." in d.symbol for d in defs)              # dotted identity
