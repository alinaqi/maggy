"""Tests for git worktree lifecycle manager."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.orchestrator.worktree import (
    create_worktree,
    list_worktrees,
    remove_worktree,
    worktree_path,
)


def test_worktree_path_sanitizes_id(tmp_path: Path) -> None:
    result = worktree_path(tmp_path, "chat/abc@123")
    assert result == tmp_path / "worktrees" / "chat_abc_123"


def test_worktree_path_preserves_safe_id(tmp_path: Path) -> None:
    result = worktree_path(tmp_path, "chat-abc.123")
    assert result == tmp_path / "worktrees" / "chat-abc.123"


@patch("maggy.orchestrator.worktree._run_git")
def test_create_worktree_calls_git(mock_git, tmp_path: Path) -> None:
    mock_git.return_value.returncode = 0
    repo = tmp_path / "repo"
    repo.mkdir()
    result = create_worktree(repo, "sess-1", tmp_path)
    expected = tmp_path / "worktrees" / "sess-1"
    assert result == expected
    calls = [c.args[0] for c in mock_git.call_args_list]
    assert any("worktree" in c and "add" in c for c in calls)


@patch("maggy.orchestrator.worktree._run_git")
def test_create_worktree_branch_name(mock_git, tmp_path: Path) -> None:
    mock_git.return_value.returncode = 0
    repo = tmp_path / "repo"
    repo.mkdir()
    create_worktree(repo, "sess-1", tmp_path)
    cmd = mock_git.call_args_list[0].args[0]
    assert "maggy/sess-1" in cmd


@patch("maggy.orchestrator.worktree._run_git")
def test_remove_worktree_calls_git(mock_git, tmp_path: Path) -> None:
    mock_git.return_value.returncode = 0
    repo = tmp_path / "repo"
    wt = tmp_path / "worktrees" / "sess-1"
    remove_worktree(repo, wt)
    cmd = mock_git.call_args.args[0]
    assert "worktree" in cmd
    assert "remove" in cmd


@patch("maggy.orchestrator.worktree._run_git")
def test_list_worktrees_parses_porcelain(mock_git, tmp_path: Path) -> None:
    mock_git.return_value.stdout = (
        "worktree /repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /tmp/wt1\nHEAD def\nbranch refs/heads/maggy/s1\n\n"
    )
    mock_git.return_value.returncode = 0
    result = list_worktrees(tmp_path / "repo")
    assert "/tmp/wt1" in result
    assert "/repo" not in result  # skip main worktree


@patch("maggy.orchestrator.worktree._run_git")
def test_list_worktrees_empty(mock_git, tmp_path: Path) -> None:
    mock_git.return_value.stdout = (
        "worktree /repo\nHEAD abc\nbranch refs/heads/main\n\n"
    )
    mock_git.return_value.returncode = 0
    result = list_worktrees(tmp_path / "repo")
    assert result == []
