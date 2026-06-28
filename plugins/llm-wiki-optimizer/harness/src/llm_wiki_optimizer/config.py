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
