# Phase 2a — Hypothesis Smoke Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal vertical slice that answers the go/no-go question — *does the llm-wiki give detectable retrieval uplift over a grep-capable agent?* — plus the two architecture checks (cross-SUT candidate-ranking correlation; test-suite + gold-extraction feasibility) and a measured Opus-calls/loop figure to recalibrate the budget.

**Architecture:** An **LLM-free** `uv`/pydantic harness in its own plugin dir (`plugins/llm-wiki-optimizer/harness/`) provides the deterministic pieces — clone the benchmark repo into a gitignored sandbox, derive single-hop Locate gold (tree-sitter), build the item bank, score set precision/recall/F1, persist to SQLite. **All model work is native Claude Code**: the SUT is a **subagent** (Sonnet / Opus) dispatched from a **dynamic Workflow** that runs the cell grid (item × candidate × tier × condition), returns structured predictions, and journals/resumes itself. A Python report step scores the predictions → uplift, plus the cross-SUT ranking and per-tier cost. **No `anthropic` SDK, no API key** — auth is the Claude Code session. This slice is the seed the full P2b harness extends.

**Tech Stack:** Python 3.12+, `uv`, pydantic v2, `tree_sitter` + `tree_sitter_python`, `sqlite3` (stdlib), pytest, ruff, `mypy --strict` for the **LLM-free** harness. Model work = **native Claude Code subagents (Sonnet + Opus) dispatched from a dynamic Workflow** — no SDK, no endpoint, no API key. The llm-wiki side stays stdlib-only and is driven via `subprocess` + its JSON contracts.

**This plan deliberately stops at the go/no-go gate.** Components whose feasibility P2a is meant to *test* (the SUT loop fidelity, the wiki build quality, the cross-SUT ranking) are built minimally and their uncertainty is named, not over-specified.

---

## File structure

```
plugins/llm-wiki-optimizer/
  harness/
    pyproject.toml                       # uv project; deps + ruff/mypy/pytest config
    .gitignore                           # .data/  (clones, gold, wiki, db — never committed)
    src/llm_wiki_optimizer/
      __init__.py
      config.py                          # pydantic models: SUT tier, Item, GoldLocation, Candidate, CellKey, CellResult
      store.py                           # SQLite cell store: idempotent upsert + "empty cells" resume
      score.py                           # symbol-set precision/recall/F1; per-item uplift
      gold/__init__.py
      gold/locate.py                     # deterministic single-hop Locate gold via tree-sitter-python
      repo.py                            # clone benchmark repo into .data/ sandbox (subprocess gh/git)
      wiki.py                            # build frozen reference wiki via `llm-wiki ingest`; ablation context
      items.py                           # build the ~20-item Locate bank from gold → .data/items.json
      report.py                          # score Workflow predictions → uplift / ranking / cost report
    workflows/
      p2a_smoke.mjs                      # the dynamic Workflow: SUT subagent over the cell grid (Sonnet/Opus)
    tests/
      fixtures/minirepo/                 # tiny Python package with known symbols (gold-extraction fixture)
      test_config.py
      test_store.py
      test_score.py
      test_gold_locate.py
```

The harness owns its deps; it never imports llm-wiki code. `.data/` is gitignored (privacy: the private repo's clone, gold, and DB never enter git).

---

## Task 1: Scaffold the uv harness project

**Files:**
- Create: `plugins/llm-wiki-optimizer/harness/pyproject.toml`
- Create: `plugins/llm-wiki-optimizer/harness/.gitignore`
- Create: `plugins/llm-wiki-optimizer/harness/src/llm_wiki_optimizer/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "llm-wiki-optimizer"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "tree-sitter>=0.23",
    "tree-sitter-python>=0.23",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
src = ["src"]

[tool.mypy]
strict = true
packages = ["llm_wiki_optimizer"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
.data/
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

- [ ] **Step 3: Create the package marker**

`src/llm_wiki_optimizer/__init__.py`:
```python
"""Overnight self-optimizer harness for the llm-wiki plugin (Phase 2a slice)."""
```

- [ ] **Step 4: Sync and verify the toolchain**

Run: `cd plugins/llm-wiki-optimizer/harness && uv sync && uv run pytest -q`
Expected: deps install; pytest reports `no tests ran` (exit 5) — the project is wired.

- [ ] **Step 5: Commit**

```bash
git add plugins/llm-wiki-optimizer/harness/pyproject.toml plugins/llm-wiki-optimizer/harness/.gitignore plugins/llm-wiki-optimizer/harness/src/llm_wiki_optimizer/__init__.py
git commit -m "feat(optimizer): scaffold uv harness project for Phase 2a"
```

---

## Task 2: Config models (pydantic)

**Files:**
- Create: `src/llm_wiki_optimizer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import pytest
from pydantic import ValidationError
from llm_wiki_optimizer.config import GoldLocation, Item, Candidate, CellKey, CellResult


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: llm_wiki_optimizer.config`.

- [ ] **Step 3: Write the implementation**

`src/llm_wiki_optimizer/config.py`:
```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator

Family = Literal["locate", "explain"]
Sut = Literal["sonnet", "opus"]
Condition = Literal["with_wiki", "ablated"]


class GoldLocation(BaseModel):
    file: str
    symbol: str            # AST-resolved dotted symbol identity (not a line string)
    start_line: int
    end_line: int


class Item(BaseModel):
    id: str
    family: Family
    hop: int
    question: str
    gold: list[GoldLocation]

    @field_validator("gold")
    @classmethod
    def _nonempty(cls, v: list[GoldLocation]) -> list[GoldLocation]:
        if not v:
            raise ValueError("gold must be non-empty for P2a Locate items")
        return v


class Candidate(BaseModel):
    """One read-prompt variant under test (the query.md body text)."""
    id: str
    prompt_text: str


class CellKey(BaseModel, frozen=True):
    item_id: str
    candidate_id: str
    sut: Sut
    condition: Condition
    seed: int


class CellResult(BaseModel):
    predicted: list[str] = Field(default_factory=list)  # predicted symbol identities
    calls: int = 0          # model calls for this cell (per-tier cost; the tier is in the CellKey)
    ok: bool = True
    error: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/llm_wiki_optimizer/config.py tests/test_config.py
git commit -m "feat(optimizer): config + result pydantic models"
```

---

## Task 3: SQLite cell store (checkpoint + idempotent resume)

**Files:**
- Create: `src/llm_wiki_optimizer/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_store.py -q`
Expected: FAIL — `ModuleNotFoundError: llm_wiki_optimizer.store`.

- [ ] **Step 3: Write the implementation**

`src/llm_wiki_optimizer/store.py`:
```python
from __future__ import annotations
import json
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_store.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/llm_wiki_optimizer/store.py tests/test_store.py
git commit -m "feat(optimizer): SQLite cell store with idempotent resume"
```

---

## Task 4: Scoring — symbol-set precision/recall/F1 + uplift

**Files:**
- Create: `src/llm_wiki_optimizer/score.py`
- Test: `tests/test_score.py`

- [ ] **Step 1: Write the failing test**

`tests/test_score.py`:
```python
import math
from llm_wiki_optimizer.score import prf1, uplift


def test_perfect_match():
    p, r, f = prf1(predicted=["a", "b"], gold=["a", "b"])
    assert (p, r, f) == (1.0, 1.0, 1.0)


def test_partial_with_distractor():
    # predicted a (gold), c (distractor); gold a,b
    p, r, f = prf1(predicted=["a", "c"], gold=["a", "b"])
    assert p == 0.5 and r == 0.5
    assert math.isclose(f, 0.5)


def test_empty_prediction_scores_zero_recall():
    p, r, f = prf1(predicted=[], gold=["a"])
    assert r == 0.0 and f == 0.0


def test_dedup_predicted():
    p, r, f = prf1(predicted=["a", "a"], gold=["a"])
    assert p == 1.0 and r == 1.0


def test_uplift_is_with_minus_ablated():
    assert uplift(with_wiki_f1=0.8, ablated_f1=0.5) == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_score.py -q`
Expected: FAIL — `ModuleNotFoundError: llm_wiki_optimizer.score`.

- [ ] **Step 3: Write the implementation**

`src/llm_wiki_optimizer/score.py`:
```python
from __future__ import annotations


def prf1(predicted: list[str], gold: list[str]) -> tuple[float, float, float]:
    """Set precision/recall/F1 over symbol identities (order-unaware, deduped)."""
    p_set, g_set = set(predicted), set(gold)
    if not p_set and not g_set:
        return 1.0, 1.0, 1.0
    tp = len(p_set & g_set)
    precision = tp / len(p_set) if p_set else 0.0
    recall = tp / len(g_set) if g_set else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def uplift(with_wiki_f1: float, ablated_f1: float) -> float:
    """Per-item uplift: what the wiki adds over the same agent without it."""
    return with_wiki_f1 - ablated_f1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_score.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/llm_wiki_optimizer/score.py tests/test_score.py
git commit -m "feat(optimizer): symbol-set scoring + uplift"
```

---

## Task 5: Deterministic single-hop Locate gold (tree-sitter)

**Files:**
- Create: `src/llm_wiki_optimizer/gold/__init__.py`
- Create: `src/llm_wiki_optimizer/gold/locate.py`
- Create fixture: `tests/fixtures/minirepo/pkg/__init__.py`, `tests/fixtures/minirepo/pkg/mod.py`
- Test: `tests/test_gold_locate.py`

This is the model-free gold backbone for P2a: "where is symbol X *defined*" → its definition location, derived from the AST. (Call-site / multi-hop gold is P2b.)

- [ ] **Step 1: Write the fixture repo**

`tests/fixtures/minirepo/pkg/__init__.py`: (empty)

`tests/fixtures/minirepo/pkg/mod.py`:
```python
def alpha(x):
    return x + 1


class Beta:
    def gamma(self):
        return alpha(2)
```

- [ ] **Step 2: Write the failing test**

`tests/test_gold_locate.py`:
```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_gold_locate.py -q`
Expected: FAIL — `ModuleNotFoundError: llm_wiki_optimizer.gold.locate`.

- [ ] **Step 4: Write the implementation**

`src/llm_wiki_optimizer/gold/__init__.py`: (empty)

`src/llm_wiki_optimizer/gold/locate.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_gold_locate.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full deterministic suite + linters**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy`
Expected: all green (the deterministic core is now fully tested).

- [ ] **Step 7: Commit**

```bash
git add src/llm_wiki_optimizer/gold tests/test_gold_locate.py tests/fixtures
git commit -m "feat(optimizer): tree-sitter single-hop Locate gold"
```

---

## Task 6: Benchmark-repo sandbox clone

**Files:**
- Create: `src/llm_wiki_optimizer/repo.py`

IO boundary — no fabricated-output unit test; verified by a real smoke run. The clone lands in the gitignored `.data/` (privacy: the private repo never enters git).

- [ ] **Step 1: Write the implementation**

`src/llm_wiki_optimizer/repo.py`:
```python
from __future__ import annotations
import subprocess
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / ".data"


def clone(repo: str, dest_name: str, ref: str | None = None) -> Path:
    """Shallow-clone `repo` (owner/name, private OK via gh auth) into .data/<dest_name>."""
    dest = DATA_DIR / dest_name
    if dest.exists():
        return dest
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = subprocess.run(
        ["gh", "repo", "view", repo, "--json", "sshUrl", "-q", ".sshUrl"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    subprocess.run(cmd, check=True)
    return dest
```

- [ ] **Step 2: Smoke-verify the clone**

Run:
```bash
uv run python -c "from llm_wiki_optimizer.repo import clone, DATA_DIR; p=clone('allada-homelab/agents-scaffold','scaffold'); print(p, p.exists())"
```
Expected: prints a path under `.data/scaffold` and `True`. Confirm `git status` at repo root shows **no** new tracked files (it is gitignored).

- [ ] **Step 3: Commit**

```bash
git add src/llm_wiki_optimizer/repo.py
git commit -m "feat(optimizer): sandbox clone of the benchmark repo"
```

---

## Task 7: Frozen reference wiki + ablation

**Files:**
- Create: `src/llm_wiki_optimizer/wiki.py`

Builds the Surface-A substrate by driving the *real* llm-wiki via subprocess (the engineering boundary). Ablation = the wiki context removed. **Uncertainty P2a tests:** that `ingest` produces a usable map-not-answer-key wiki at a tractable cost — verify, don't assume.

- [ ] **Step 1: Write the implementation**

`src/llm_wiki_optimizer/wiki.py`:
```python
from __future__ import annotations
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[4] / "plugins" / "llm-wiki"


def doctor_ok(bundle: Path) -> bool:
    r = subprocess.run(
        ["python3", str(PLUGIN / "scripts" / "doctor.py"), str(bundle),
         "--mode", "strict", "--format", "text"],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def wiki_context(bundle: Path) -> str:
    """The with-wiki preload: the root index.md body (what SessionStart injects)."""
    index = bundle / "index.md"
    return index.read_text() if index.exists() else ""


def ablated_context() -> str:
    """The wiki-ablated condition: no wiki in context."""
    return ""
```

- [ ] **Step 2: Build the reference wiki (manual procedure for P2a)**

Inside a fresh Claude Code session at the repo root, run `/llm-wiki:ingest .data/scaffold --scope medium --bundle .data/scaffold-wiki`. (P2a uses the existing ingest command; automating ingest is P2b.) Then verify:

Run: `uv run python -c "from llm_wiki_optimizer.wiki import doctor_ok; from pathlib import Path; print(doctor_ok(Path('.data/scaffold-wiki')))"`
Expected: `True` (the substrate is OKF-conformant). Eyeball that concepts are *orienting* (architecture/subsystems), **not** verbatim gold locations.

- [ ] **Step 3: Commit**

```bash
git add src/llm_wiki_optimizer/wiki.py
git commit -m "feat(optimizer): reference-wiki context + ablation + Doctor check"
```

---

## Task 8: SUT subagent + smoke Workflow (native Claude Code)

**Files:**
- Create: `src/llm_wiki_optimizer/sut_agent.md` (the SUT subagent brief)
- Create: `plugins/llm-wiki-optimizer/harness/workflows/p2a_smoke.mjs` (the dynamic Workflow)

The SUT is a **real Claude Code subagent** (read-only `Explore` type — Grep/Read tools), dispatched from a **dynamic Workflow** over the cell grid. No hand-rolled loop, no API, no key — the agent *is* the read loop, maximally faithful to deployed llm-wiki. Each cell forces a structured prediction via a `schema`; a dead agent returns `null` (fail-open). The tier (`sonnet`/`opus`) is the agent's `model`.

- [ ] **Step 1: Write the SUT subagent brief**

`src/llm_wiki_optimizer/sut_agent.md` — the read-only agent that answers one Locate item. The Workflow composes the final prompt per cell (prepending the candidate prompt + question, and — for `with_wiki` — the wiki index + bundle path):

```markdown
You answer ONE code-location question about a repository, read-only.

- Use **Grep** and **Read** to locate the answer; ground every symbol in code you actually read.
- If a knowledge wiki is provided, read its index and the relevant concept files to orient FIRST,
  then confirm the exact locations in code.
- Return the **dotted symbol identities** (e.g. `pkg.mod.func`) that answer the question — an empty
  list if none are present. Write nothing.
```

- [ ] **Step 2: Write the smoke Workflow**

`plugins/llm-wiki-optimizer/harness/workflows/p2a_smoke.mjs` — invoked via the Workflow tool with `args = { items, candidates, wikiContext, wikiBundlePath, repoPath }`:

```javascript
export const meta = {
  name: 'p2a-smoke',
  description: 'P2a smoke: SUT subagent over the cell grid (with-wiki vs ablated, Sonnet vs Opus)',
  phases: [{ title: 'SUT grid' }],
}

const PRED_SCHEMA = {
  type: 'object',
  required: ['predicted'],
  properties: {
    predicted: {
      type: 'array', items: { type: 'string' },
      description: 'dotted symbol identities (e.g. pkg.mod.func) that answer the question; [] if none',
    },
  },
}

const brief = (cand, question, repoPath, wiki, bundle) =>
  `${cand.prompt_text}\n\n` +
  `Answer ONE code-location question about the repository at ${repoPath}, read-only.\n` +
  `Use Grep and Read to ground every symbol in code you actually read.\n` +
  (wiki
    ? `A knowledge wiki for this repo is at ${bundle}; its index:\n${wiki}\n` +
      `Read the relevant concept files to orient FIRST, then confirm exact locations in code.\n`
    : '') +
  `QUESTION: ${question}\n` +
  `Return the dotted symbol identities that answer it (empty list if none).`

// Ablated reference is candidate-independent (no wiki) — the cacheable baseline; comparing each
// candidate's with-wiki score against a FIXED no-wiki bar avoids the "win uplift by being a bad
// no-wiki prompt" gaming.
const BASELINE = { id: '__baseline__', prompt_text: 'Find the code locations that answer the question.' }

phase('SUT grid')

const cells = []
for (const item of args.items)
  for (const sut of ['sonnet', 'opus']) {
    cells.push({ item, cand: BASELINE, sut, cond: 'ablated' })        // one per item×tier
    for (const cand of args.candidates)                              // with-wiki: one per candidate
      cells.push({ item, cand, sut, cond: 'with_wiki' })
  }

const out = await parallel(cells.map((c) => () =>
  agent(
    brief(c.cand, c.item.question, args.repoPath,
          c.cond === 'with_wiki' ? args.wikiContext : '', args.wikiBundlePath),
    { label: `sut:${c.sut}:${c.cond}:${c.item.id}:${c.cand.id}`,
      model: c.sut, agentType: 'Explore', schema: PRED_SCHEMA },
  ).then((r) => ({
    item_id: c.item.id, candidate_id: c.cand.id, sut: c.sut, condition: c.cond,
    predicted: r ? r.predicted : [], ok: r !== null,
  }))
))

return { cells: out }
```

- [ ] **Step 3: Smoke-verify one cell via the Workflow tool**

Invoke the Workflow tool with `p2a_smoke.mjs` and a 1-item / 1-candidate `args` (it still fans `sonnet`×`opus` × `with_wiki`×`ablated` = 4 cells). Expected: it returns `{cells: [...]}` with a `predicted` symbol list per cell and no stall. This proves the subagent + schema + tiering wiring; full-grid fidelity is judged in Task 9.

- [ ] **Step 4: Commit**

```bash
git add src/llm_wiki_optimizer/sut_agent.md plugins/llm-wiki-optimizer/harness/workflows/p2a_smoke.mjs
git commit -m "feat(optimizer): SUT subagent + p2a smoke Workflow (native Claude Code)"
```

---

## Task 9: Item bank + score + go/no-go report

**Files:**
- Create: `src/llm_wiki_optimizer/items.py`
- Create: `src/llm_wiki_optimizer/report.py`

Build the ~20-item bank, run the smoke Workflow (Task 8) via the Workflow tool, and score its predictions → the three P2a answers. Grid = ~20 single-hop Locate items × {with_wiki, ablated} × {sonnet, opus} × ~3 candidates.

- [ ] **Step 1: Write `items.py` and build the bank**

`src/llm_wiki_optimizer/items.py`:
```python
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
```
Run: `uv run python -c "from pathlib import Path; from llm_wiki_optimizer.items import build; print(len(build(Path('.data/scaffold'), Path('.data/items.json'))))"`
Expected: ~20. Gold is the AST-derived dotted symbol (model-free); the question is a template. *(Single-hop navigational Locate has the identifier in the question by design; absent-identifier / obfuscated strata are P2b, not the smoke test.)*

- [ ] **Step 2: Write `report.py`**

`src/llm_wiki_optimizer/report.py`:
```python
from __future__ import annotations
import json
import statistics
from pathlib import Path
from llm_wiki_optimizer.config import Item
from llm_wiki_optimizer.score import prf1, uplift


def _f1(cell: dict, gold: list[str]) -> float:
    if not cell.get("ok", False):
        return 0.0
    return prf1(cell["predicted"], gold)[2]


def report(items_path: Path, cells_path: Path) -> dict:
    items = {d["id"]: Item.model_validate(d) for d in json.loads(items_path.read_text())}
    cells = json.loads(cells_path.read_text())["cells"]
    idx = {(c["item_id"], c["candidate_id"], c["sut"], c["condition"]): c for c in cells}
    cand_ids = sorted({c["candidate_id"] for c in cells})

    def f1(item_id: str, cand: str, sut: str, cond: str) -> float:
        c = idx.get((item_id, cand, sut, cond))
        return 0.0 if c is None else _f1(c, [g.symbol for g in items[item_id].gold])

    real = [c for c in cand_ids if c != "__baseline__"]
    out: dict = {}
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
```
*(Scoring stays in the tested `score.py`; `report.py` only aggregates the Workflow's predictions. Per-tier **cost** comes from the Workflow run's token-usage summary, read by the orchestrating agent — not from `report.py`. The SQLite `store` (Task 3) archives cells for P2b durability; P2a's report reads the Workflow's returned JSON directly.)*

- [ ] **Step 3: Run the smoke Workflow, then score**

The orchestrating Claude Code agent: (a) builds the reference wiki (Task 7) and reads its `index.md` body; (b) **invokes the Workflow tool** with `workflows/p2a_smoke.mjs` and `args = { items, candidates, wikiContext: <index.md body>, wikiBundlePath: ".data/scaffold-wiki", repoPath: ".data/scaffold" }` (3 hand-made candidates from the design's §2 read-prompt examples); (c) writes the returned `{cells}` to `.data/p2a_cells.json` **and** records the Workflow's per-tier **token usage**; (d) runs the report:
```bash
uv run python -c "from pathlib import Path; import json; from llm_wiki_optimizer.report import report; print(json.dumps(report(Path('.data/items.json'), Path('.data/p2a_cells.json')), indent=2))"
```
Expected: a JSON report. Read it against the **go/no-go criteria** below. (The Workflow journals every cell — a stopped run resumes via `resumeFromRunId`, recomputing only unfinished cells.)

- [ ] **Step 4: Decide go/no-go (the gate)**

- **(i) Hypothesis:** `mean_uplift_sonnet` and/or `mean_uplift_opus` is **detectably positive** (a clear margin over 0 across the 20 items). If ~0 or negative on both → **NO-GO**: the wiki adds nothing over a grep-capable agent; stop and rethink the premise before building P2b.
- **(ii) Cross-SUT ranking:** the candidate orderings from `candidate_scores_sonnet` vs `candidate_scores_opus` **agree**. If they disagree → the cheap-search/expensive-gate architecture is invalid; Opus must enter the search loop (revise §5 + budget).
- **(iii) Feasibility + cost:** the Workflow completed without stalls (dead agents fail-open to `null`); its **per-tier token usage** (from the run summary) gives the real cost/cell to **recalibrate `max_sonnet_calls` + `max_opus_api_calls` and estimate the overnight $**. Separately confirm `agents-scaffold`'s test suite runs green locally (the anchor depends on it).

- [ ] **Step 5: Commit + record the verdict**

```bash
git add src/llm_wiki_optimizer/items.py src/llm_wiki_optimizer/report.py
git commit -m "feat(optimizer): P2a item bank + report (uplift/ranking/cost)"
```

Then write the verdict (the JSON report + the three decisions + the recalibrated budget) into `docs/llm-wiki/optimizer/self-optimizer-design.md` (update §2 budget + §9 P2a row), and report to the user. **Do not start P2b until P2a returns GO.**

---

## Self-review

- **Spec coverage (vs design §9 P2a):** (i) hypothesis uplift — Tasks 5,7,8,9; (ii) cross-SUT ranking correlation — Task 9 report; (iii) test-suite + gold feasibility — Tasks 5,6 + Task 9 Step 4; per-tier token/cost recalibration — Task 9. Reference wiki — Task 7. Privacy (`.data/` gitignored) — Tasks 1,6. Robustness: SUT is a read-only subagent in a **journaled Workflow** (fail-open via `null`) — Task 8. ✓
- **Deferred to P2b (named, not gaps):** multi-hop + call-graph gold; Explain family; the statistical gate (Wilcoxon/BH); GEPA-style + random optimizer (as Workflows); the supervised overnight run (chained Workflows + scheduled wake); the judge; fastapi transfer; automated ingest. P2a is the kill-switch slice only.
- **Type consistency:** `CellKey`/`CellResult`/`Item`/`GoldLocation`/`Candidate` are defined once in Task 2 and used unchanged in Tasks 3,5,9; `prf1`→3-tuple and `definitions(root)→list[GoldLocation]` signatures match their call sites; the Workflow returns `{cells:[{item_id,candidate_id,sut,condition,predicted,ok}]}`, which `report.py` indexes by exactly those keys. ✓
- **Honesty:** Tasks 6–9 are IO/agentic boundaries verified by smoke runs, not fabricated-output unit tests — called out explicitly; the deterministic core (Tasks 2–5) is real TDD. The SUT subagent + Workflow (Task 8) is authored/run via the Workflow tool, not unit-tested in isolation.
