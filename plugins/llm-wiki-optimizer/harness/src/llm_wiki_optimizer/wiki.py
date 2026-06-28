from __future__ import annotations
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[5] / "plugins" / "llm-wiki"  # public-skills/plugins/llm-wiki


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
