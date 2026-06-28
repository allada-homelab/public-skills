# Phase 2a — Hypothesis Smoke Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal vertical slice that answers the go/no-go question — *does the llm-wiki give detectable retrieval uplift over a grep-capable agent?* — plus the two architecture checks (cross-SUT candidate-ranking correlation; test-suite + gold-extraction feasibility) and a measured Opus-calls/loop figure to recalibrate the budget.

**Architecture:** A standalone `uv`/pydantic harness in its own plugin dir (`plugins/llm-wiki-optimizer/harness/`) that drives the *stdlib-only* llm-wiki via subprocess only. It clones the benchmark repo into a gitignored sandbox, derives single-hop Locate gold deterministically (tree-sitter), builds a frozen reference wiki via `llm-wiki ingest`, runs a bounded read-loop SUT (vLLM + Anthropic backends) in with-wiki vs wiki-ablated conditions across a few hand-made read-prompt candidates, scores set precision/recall/F1 → uplift, checkpoints every cell to SQLite, and emits a go/no-go report. This slice is the seed the full P2b harness extends.

**Tech Stack:** Python 3.12+, `uv`, pydantic v2, `httpx` (vLLM OpenAI-compatible), `anthropic` SDK, `tree_sitter` + `tree_sitter_python`, `sqlite3` (stdlib), pytest, ruff, `mypy --strict`. The llm-wiki side stays stdlib-only and is driven via `subprocess` + its JSON contracts.

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
      config.py                          # pydantic models: paths, SUT/backend config, Item, GoldLocation, Candidate, CellKey, CellResult
      store.py                           # SQLite cell store: idempotent upsert + "empty cells" resume
      score.py                           # symbol-set precision/recall/F1; per-item uplift
      gold/__init__.py
      gold/locate.py                     # deterministic single-hop Locate gold via tree-sitter-python
      repo.py                            # clone benchmark repo into .data/ sandbox (subprocess gh/git)
      wiki.py                            # build frozen reference wiki via `llm-wiki ingest`; ablation context
      backends.py                        # LLM call: vLLM (httpx, OpenAI-compatible) + Anthropic; timeout+retry; call counter
      sut.py                             # bounded read-loop agent (grep/read tools) → answer location set
      smoke.py                           # P2a orchestration + go/no-go report (CLI entrypoint)
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
    "httpx>=0.27",
    "anthropic>=0.40",
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
    k1 = CellKey(item_id="i1", candidate_id="c1", sut="vllm", condition="with_wiki", seed=0)
    k2 = CellKey(item_id="i1", candidate_id="c1", sut="vllm", condition="with_wiki", seed=0)
    assert k1 == k2 and hash(k1) == hash(k2)


def test_cellresult_carries_locations_and_cost():
    r = CellResult(predicted=["pkg.mod.func"], opus_calls=3, ok=True, error=None)
    assert r.predicted == ["pkg.mod.func"]
    assert r.opus_calls == 3
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
Sut = Literal["vllm", "opus"]
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
    opus_calls: int = 0
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
    return CellKey(item_id="i1", candidate_id="c1", sut="vllm", condition="with_wiki", seed=seed)


def test_put_then_get_roundtrips(tmp_path: Path):
    s = CellStore(tmp_path / "run.db")
    s.put(_key(), CellResult(predicted=["a.b"], opus_calls=2))
    got = s.get(_key())
    assert got is not None and got.predicted == ["a.b"] and got.opus_calls == 2


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

## Task 8: Bounded read-loop SUT (vLLM + Anthropic backends)

**Files:**
- Create: `src/llm_wiki_optimizer/backends.py`
- Create: `src/llm_wiki_optimizer/sut.py`

The only agentic loop, hard-capped on iterations + wall-clock (the robustness defense). Backends share one interface; each call has a timeout + bounded retry and increments an Opus-call counter (for budget recalibration).

- [ ] **Step 1: Write `backends.py`**

`src/llm_wiki_optimizer/backends.py`:
```python
from __future__ import annotations
import os
from dataclasses import dataclass, field
import httpx
import anthropic


@dataclass
class CallCounter:
    opus_calls: int = 0


@dataclass
class Backend:
    sut: str                       # "vllm" | "opus"
    model: str
    counter: CallCounter = field(default_factory=CallCounter)
    timeout_s: float = 120.0

    def chat(self, system: str, user: str) -> str:
        for attempt in range(3):
            try:
                if self.sut == "opus":
                    self.counter.opus_calls += 1
                    client = anthropic.Anthropic()
                    msg = client.messages.create(
                        model=self.model, max_tokens=1024,
                        system=system, messages=[{"role": "user", "content": user}],
                        timeout=self.timeout_s,
                    )
                    return "".join(b.text for b in msg.content if b.type == "text")
                resp = httpx.post(
                    f"{os.environ['VLLM_ENDPOINT']}/v1/chat/completions",
                    json={"model": self.model, "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}]},
                    timeout=self.timeout_s,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception:  # noqa: BLE001 — bounded retry, then mark-failed upstream
                if attempt == 2:
                    raise
        raise RuntimeError("unreachable")
```

- [ ] **Step 2: Write `sut.py`**

`src/llm_wiki_optimizer/sut.py`:
```python
from __future__ import annotations
import json
import re
import subprocess
import time
from pathlib import Path
from llm_wiki_optimizer.backends import Backend
from llm_wiki_optimizer.config import CellResult

MAX_ITERS = 6
MAX_WALL_S = 180.0

_SYSTEM = (
    "You answer code-location questions about a repository. Tools: "
    "`GREP <pattern>` searches the repo; `READ <path>` reads a file. "
    "When done, output a single line `ANSWER: <json list of dotted symbol identities>`. "
    "Ground every answer in files you READ; if nothing covers it, output `ANSWER: []`."
)


def _tool(line: str, repo: Path) -> str:
    if line.startswith("GREP "):
        pat = line[5:].strip()
        r = subprocess.run(["grep", "-rn", pat, str(repo)], capture_output=True, text=True)
        return r.stdout[:4000]
    if line.startswith("READ "):
        p = repo / line[5:].strip()
        return p.read_text()[:6000] if p.exists() else "NOT FOUND"
    return "UNKNOWN TOOL"


def run_item(backend: Backend, prompt_text: str, wiki_context: str,
             question: str, repo: Path) -> CellResult:
    """Bounded read loop → predicted symbol list. Hard caps defend against hangs."""
    transcript = f"{prompt_text}\n\n{wiki_context}\n\nQUESTION: {question}\n"
    started = time.monotonic()
    try:
        for _ in range(MAX_ITERS):
            if time.monotonic() - started > MAX_WALL_S:
                return CellResult(ok=False, error="wall-clock cap")
            out = backend.chat(system=_SYSTEM, user=transcript)
            m = re.search(r"ANSWER:\s*(\[.*\])", out)
            if m:
                preds = [str(s) for s in json.loads(m.group(1))]
                return CellResult(predicted=preds, opus_calls=backend.counter.opus_calls)
            cmd = out.strip().splitlines()[-1] if out.strip() else ""
            transcript += f"\n{out}\nTOOL RESULT:\n{_tool(cmd, repo)}\n"
        return CellResult(ok=False, error="iteration cap")
    except Exception as e:  # noqa: BLE001 — fail open toward progress
        return CellResult(ok=False, error=str(e)[:200])
```

- [ ] **Step 3: Smoke-verify one item end-to-end (vLLM)**

Run (with `VLLM_ENDPOINT` set):
```bash
uv run python -c "
from pathlib import Path
from llm_wiki_optimizer.backends import Backend
from llm_wiki_optimizer.sut import run_item
b = Backend(sut='vllm', model='<your-vllm-model>')
r = run_item(b, 'Find the definitions.', '', 'Where is the function alpha defined?', Path('tests/fixtures/minirepo'))
print(r)
"
```
Expected: a `CellResult` whose `predicted` contains a plausible symbol; no hang (returns within the caps). This proves the loop + tool wiring; fidelity is judged in Task 9.

- [ ] **Step 4: Commit**

```bash
git add src/llm_wiki_optimizer/backends.py src/llm_wiki_optimizer/sut.py
git commit -m "feat(optimizer): bounded read-loop SUT with vLLM/Anthropic backends"
```

---

## Task 9: P2a orchestration + go/no-go report

**Files:**
- Create: `src/llm_wiki_optimizer/smoke.py`

Runs the grid and answers the three P2a questions. ~20 single-hop Locate items × {with_wiki, ablated} × {vllm, opus} × ~3 read-prompt candidates × 1 seed, every cell checkpointed.

- [ ] **Step 1: Assemble the ~20-item bank**

Procedure: call `gold.locate.definitions(.data/scaffold)`, sample ~20 definitions, and for each phrase a question ("Where is `<name>` defined?") — gold is the dotted symbol (NOT phrased by a model; the question is a template). Persist the bank as `.data/items.json` (list of `Item`). Filter out any symbol whose name is a unique exact-string trivially greppable in one hit (too-easy guard).

- [ ] **Step 2: Write `smoke.py`**

`src/llm_wiki_optimizer/smoke.py`:
```python
from __future__ import annotations
import itertools
import json
import statistics
from pathlib import Path
from llm_wiki_optimizer.backends import Backend, CallCounter
from llm_wiki_optimizer.config import Candidate, CellKey, Item
from llm_wiki_optimizer.score import prf1, uplift
from llm_wiki_optimizer.store import CellStore
from llm_wiki_optimizer.sut import run_item
from llm_wiki_optimizer.wiki import wiki_context, ablated_context

REPO = Path(".data/scaffold")
WIKI = Path(".data/scaffold-wiki")


def _candidates() -> list[Candidate]:
    return [
        Candidate(id="baseline", prompt_text="Find the code locations that answer the question."),
        Candidate(id="map-first", prompt_text="First read the wiki to orient, then grep to confirm exact locations."),
        Candidate(id="terse", prompt_text="Locate the definition. Answer only with symbol identities."),
    ]


def _models(sut: str) -> str:
    return {"vllm": "<your-vllm-model>", "opus": "claude-opus-4-8"}[sut]


def run(db: Path) -> dict[str, object]:
    items = [Item.model_validate(d) for d in json.loads(Path(".data/items.json").read_text())]
    cands = _candidates()
    store = CellStore(db)
    ctx = {"with_wiki": wiki_context(WIKI), "ablated": ablated_context()}

    for item, cand, sut, cond in itertools.product(items, cands, ("vllm", "opus"), ctx):
        key = CellKey(item_id=item.id, candidate_id=cand.id, sut=sut, condition=cond, seed=0)
        if store.get(key) is not None:
            continue
        backend = Backend(sut=sut, model=_models(sut), counter=CallCounter())
        store.put(key, run_item(backend, cand.prompt_text, ctx[cond], item.question, REPO))

    return _report(items, cands, store)


def _f1(store: CellStore, item: Item, cand: Candidate, sut: str, cond: str) -> float:
    res = store.get(CellKey(item_id=item.id, candidate_id=cand.id, sut=sut, condition=cond, seed=0))
    if res is None or not res.ok:
        return 0.0
    gold = [g.symbol for g in item.gold]
    return prf1(res.predicted, gold)[2]


def _report(items: list[Item], cands: list[Candidate], store: CellStore) -> dict[str, object]:
    out: dict[str, object] = {}
    # (1) detectable uplift per SUT (mean per-item with_wiki - ablated, best candidate)
    for sut in ("vllm", "opus"):
        ups = [max(uplift(_f1(store, it, c, sut, "with_wiki"), _f1(store, it, c, sut, "ablated"))
                   for c in cands) for it in items]
        out[f"mean_uplift_{sut}"] = round(statistics.mean(ups), 4)
    # (2) cross-SUT candidate-ranking correlation (with_wiki mean F1 per candidate)
    def cand_scores(sut: str) -> list[float]:
        return [statistics.mean(_f1(store, it, c, sut, "with_wiki") for it in items) for c in cands]
    out["candidate_scores_vllm"] = cand_scores("vllm")
    out["candidate_scores_opus"] = cand_scores("opus")
    out["ranking_note"] = "compare the two orderings; low correlation invalidates cheap-search/expensive-gate"
    # (3) measured Opus calls/loop
    opus_calls = [store.get(CellKey(item_id=it.id, candidate_id=c.id, sut="opus",
                                    condition=cond, seed=0)).opus_calls
                  for it in items for c in cands for cond in ("with_wiki", "ablated")
                  if store.get(CellKey(item_id=it.id, candidate_id=c.id, sut="opus",
                                       condition=cond, seed=0)) is not None]
    out["opus_calls_per_loop_max"] = max(opus_calls) if opus_calls else 0
    return out


if __name__ == "__main__":
    print(json.dumps(run(Path(".data/p2a.db")), indent=2))
```

- [ ] **Step 3: Run the smoke test**

Run: `uv run python -m llm_wiki_optimizer.smoke`
Expected: a JSON report. Read it against the **go/no-go criteria** below.

- [ ] **Step 4: Decide go/no-go (the gate)**

- **(i) Hypothesis:** `mean_uplift_vllm` and/or `mean_uplift_opus` is **detectably positive** (a clear margin over 0 across the 20 items). If ~0 or negative on both → **NO-GO**: the wiki adds nothing over a grep-capable agent; stop and rethink the premise before building P2b.
- **(ii) Cross-SUT ranking:** the candidate orderings from `candidate_scores_vllm` vs `candidate_scores_opus` **agree**. If they disagree → the cheap-search/expensive-gate architecture is invalid; Opus must enter the search loop (revise §5 + budget).
- **(iii) Feasibility:** the run completed without hangs (caps held); `opus_calls_per_loop_max` gives the real figure to **recalibrate `max_opus_api_calls`** in the design. Separately confirm `agents-scaffold`'s test suite runs green locally (the anchor depends on it).

- [ ] **Step 5: Commit + record the verdict**

```bash
git add src/llm_wiki_optimizer/smoke.py
git commit -m "feat(optimizer): P2a smoke-test orchestration + go/no-go report"
```

Then write the verdict (the JSON report + the three decisions + the recalibrated budget) into `docs/llm-wiki/optimizer/self-optimizer-design.md` (update §2 budget + §9 P2a row), and report to the user. **Do not start P2b until P2a returns GO.**

---

## Self-review

- **Spec coverage (vs design §9 P2a):** (i) hypothesis uplift — Tasks 5,7,8,9; (ii) cross-SUT ranking correlation — Task 9 report; (iii) test-suite + gold feasibility — Tasks 5,6 + Task 9 Step 4; Opus-calls recalibration — Task 9. Reference wiki — Task 7. Privacy (`.data/` gitignored) — Tasks 1,6. Robustness caps in the only agentic loop — Task 8. ✓
- **Deferred to P2b (named, not gaps):** multi-hop + call-graph gold; Explain family; the statistical gate (Wilcoxon/BH); GEPA/random optimizer; the daemon/supervisor + watchdog; the judge; fastapi transfer; automated ingest. P2a is the kill-switch slice only.
- **Type consistency:** `CellKey`/`CellResult`/`Item`/`GoldLocation`/`Candidate` are defined once in Task 2 and used unchanged in Tasks 3,5,8,9; `prf1`→3-tuple and `definitions(root)→list[GoldLocation]` signatures match their call sites; `Backend.chat`/`run_item` signatures match Task 9 usage. ✓
- **Honesty:** Tasks 6–9 are IO/agentic boundaries verified by smoke runs, not fabricated-output unit tests — called out explicitly; the deterministic core (Tasks 2–5) is real TDD.
