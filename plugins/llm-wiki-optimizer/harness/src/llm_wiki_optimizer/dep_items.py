from __future__ import annotations
import json
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from llm_wiki_optimizer.config import GoldLocation, Item
from llm_wiki_optimizer.gold.locate import definitions

_LANG = Language(tspython.language())
_PARSER = Parser(_LANG)


def _matches_module(name: str, module_dotted: str, last_seg: str) -> bool:
    return name == module_dotted or name.endswith("." + last_seg)


def _tree_imports_module(root_node: Node, module_dotted: str) -> bool:
    """Return True if the parsed AST contains an import of module_dotted."""
    last_seg = module_dotted.rsplit(".", 1)[-1]

    def walk(node: Node) -> bool:
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "dotted_name" and child.text is not None:
                    if _matches_module(child.text.decode(), module_dotted, last_seg):
                        return True
                elif child.type == "aliased_import":
                    # `import X.Y as z` — the dotted_name is the first named child
                    name_node = child.child_by_field_name("name")
                    if name_node is None:
                        for sub in child.named_children:
                            if sub.type == "dotted_name":
                                name_node = sub
                                break
                    if name_node is not None and name_node.text is not None:
                        if _matches_module(name_node.text.decode(), module_dotted, last_seg):
                            return True
            return False
        if node.type == "import_from_statement":
            # `from X import Y` — source module is under field "module_name"
            mod_node = node.child_by_field_name("module_name")
            if mod_node is None:
                for child in node.named_children:
                    if child.type in ("dotted_name", "relative_import"):
                        mod_node = child
                        break
            if mod_node is not None and mod_node.text is not None:
                return _matches_module(mod_node.text.decode(), module_dotted, last_seg)
            return False
        return any(walk(child) for child in node.children)

    return walk(root_node)


def importers(root: Path, module_dotted: str) -> list[str]:
    """Return sorted repo-relative paths of .py files that import module_dotted.

    The file defining the module itself is excluded.
    Matching is lenient: `import X.Y`, `import X.Y as z`, and `from X.Y import ...`
    all match when X.Y equals module_dotted or ends with .<last_segment>.
    """
    defining_rel = module_dotted.replace(".", "/") + ".py"
    defining_init = module_dotted.replace(".", "/") + "/__init__.py"

    result: list[str] = []
    for py_file in sorted(root.rglob("*.py")):
        rel = str(py_file.relative_to(root))
        if rel in (defining_rel, defining_init):
            continue
        tree = _PARSER.parse(py_file.read_bytes())
        if _tree_imports_module(tree.root_node, module_dotted):
            result.append(rel)
    return sorted(result)


def _file_to_module(rel_file: str) -> str:
    """Convert a repo-relative .py path to a dotted module path."""
    p = Path(rel_file).with_suffix("")
    parts = [seg for seg in p.parts if seg != "__init__"]
    return ".".join(parts)


def build_dep_items(root: Path, out: Path, limit: int = 15) -> list[Item]:
    """Build dependency-impact items from tree-sitter import analysis.

    For each module that has >= 3 importers, emit an Item asking which files
    would need to be checked if that module's public interface changes.
    """
    defs = definitions(root)
    seen_modules: set[str] = set()
    unique_files = sorted({d.file for d in defs})

    items: list[Item] = []
    dep_idx = 0
    for rel_file in unique_files:
        module_dotted = _file_to_module(rel_file)
        if not module_dotted or module_dotted in seen_modules:
            continue
        seen_modules.add(module_dotted)

        importer_files = importers(root, module_dotted)
        if len(importer_files) < 3:
            continue

        gold = [
            GoldLocation(file=f, symbol=f, start_line=0, end_line=0)
            for f in importer_files
        ]
        question = (
            f"A developer wants to change the public interface of the "
            f"`{module_dotted}` module. Which source files import or depend on it "
            f"and would need to be checked? List the repo-relative file paths."
        )
        items.append(
            Item(
                id=f"dep{dep_idx}",
                family="explain",
                hop=len(importer_files),
                question=question,
                gold=gold,
            )
        )
        dep_idx += 1
        if len(items) >= limit:
            break

    out.write_text(json.dumps([it.model_dump() for it in items], indent=2))
    return items
