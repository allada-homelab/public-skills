from __future__ import annotations
import subprocess
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / ".data"  # harness/.data (covered by harness/.gitignore)


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
