from __future__ import annotations
from pathlib import Path
import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser
from llm_wiki_optimizer.config import GoldLocation

_LANG = Language(tspython.language())
_PARSER = Parser(_LANG)


def _module_path(py_file: Path, root: Path) -> str:
    rel = py_file.relative_to(root).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(parts)


def _walk_defs(node: Node, prefix: str, rel_file: str, out: list[GoldLocation]) -> None:
    for child in node.children:
        if child.type in ("function_definition", "class_definition"):
            name_node = child.child_by_field_name("name")
            if name_node is not None and name_node.text is not None:
                name = name_node.text.decode()
                symbol = f"{prefix}.{name}" if prefix else name
                out.append(GoldLocation(
                    file=rel_file, symbol=symbol,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                ))
                body = child.child_by_field_name("body")
                if body is not None:
                    _walk_defs(body, symbol, rel_file, out)
        else:
            _walk_defs(child, prefix, rel_file, out)


def definitions(root: Path) -> list[GoldLocation]:
    """All function/class/method definitions under `root`, as dotted symbol gold."""
    out: list[GoldLocation] = []
    for py_file in sorted(root.rglob("*.py")):
        rel_file = str(py_file.relative_to(root))
        mod = _module_path(py_file, root)
        tree = _PARSER.parse(py_file.read_bytes())
        _walk_defs(tree.root_node, mod, rel_file, out)
    return out
