"""merge_changes captures every change made in an isolated workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maggy.orchestrator.merge import merge_changes
from maggy.orchestrator.worktree import create_worktree


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("base\n")
    (root / ".gitignore").write_text("*.log\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _commit(ws: Path, name: str, text: str) -> None:
    (ws / name).write_text(text)
    _git(ws, "add", name)
    _git(ws, "commit", "-qm", f"add {name}")


def test_captures_commits_uncommitted_and_untracked(repo, tmp_path):
    ws = create_worktree(repo, "s1", tmp_path / "ws")
    _commit(ws, "one.txt", "first\n")
    _commit(ws, "two.txt", "second\n")
    (ws / "a.txt").write_text("edited, not committed\n")
    (ws / "new.txt").write_text("untracked\n")
    (ws / "debug.log").write_text("ignored\n")
    assert merge_changes(repo, ws) is True
    assert (repo / "one.txt").read_text() == "first\n"
    assert (repo / "two.txt").read_text() == "second\n"
    assert (repo / "a.txt").read_text() == "edited, not committed\n"
    assert (repo / "new.txt").read_text() == "untracked\n"
    assert not (repo / "debug.log").exists()


def test_no_changes_is_success(repo, tmp_path):
    ws = create_worktree(repo, "s2", tmp_path / "ws")
    assert merge_changes(repo, ws) is True


def test_conflict_reports_failure(repo, tmp_path):
    ws = create_worktree(repo, "s3", tmp_path / "ws")
    (ws / "a.txt").write_text("workspace\n")
    (repo / "a.txt").write_text("repo dirty edit\n")
    assert merge_changes(repo, ws) is False


def test_missing_workspace_reports_failure(repo, tmp_path):
    assert merge_changes(repo, tmp_path / "nope") is False
