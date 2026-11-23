"""Shared git fixtures for merge_changes tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("base\n")
    (root / ".gitignore").write_text("*.log\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return root


def commit(ws: Path, name: str, text: str) -> None:
    (ws / name).write_text(text)
    git(ws, "add", name)
    git(ws, "commit", "-qm", f"add {name}")


def three_line_repo(repo: Path) -> None:
    (repo / "a.txt").write_text("1\n2\n3\n")
    git(repo, "commit", "-qam", "three lines")
