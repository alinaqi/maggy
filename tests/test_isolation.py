"""Tests for isolation strategy resolver."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.orchestrator.isolation import (
    IsolationLevel,
    cleanup_workspace,
    detect_capabilities,
    provision_workspace,
)


def test_isolation_level_values() -> None:
    assert IsolationLevel.CONTAINER.value == "container"
    assert IsolationLevel.WORKTREE.value == "worktree"
    assert IsolationLevel.LOCK_ONLY.value == "lock_only"


@patch("shutil.which")
def test_detect_docker_available(mock_which) -> None:
    mock_which.side_effect = lambda x: "/usr/bin/docker" if x == "docker" else "/usr/bin/git"
    result = detect_capabilities()
    assert result == IsolationLevel.CONTAINER


@patch("shutil.which")
def test_detect_git_only(mock_which) -> None:
    mock_which.side_effect = lambda x: "/usr/bin/git" if x == "git" else None
    result = detect_capabilities()
    assert result == IsolationLevel.WORKTREE


@patch("shutil.which")
def test_detect_nothing(mock_which) -> None:
    mock_which.return_value = None
    result = detect_capabilities()
    assert result == IsolationLevel.LOCK_ONLY


@patch("maggy.orchestrator.worktree.create_worktree")
def test_provision_worktree(mock_create, tmp_path: Path) -> None:
    mock_create.return_value = tmp_path / "wt"
    result = provision_workspace(
        IsolationLevel.WORKTREE, tmp_path / "repo", "s1", tmp_path,
    )
    assert result == str(tmp_path / "wt")
    mock_create.assert_called_once()


def test_provision_lock_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = provision_workspace(
        IsolationLevel.LOCK_ONLY, repo, "s1", tmp_path,
    )
    assert result == str(repo)


@patch("maggy.orchestrator.worktree.remove_worktree")
def test_cleanup_worktree(mock_remove, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    ws = tmp_path / "wt"
    cleanup_workspace(IsolationLevel.WORKTREE, repo, str(ws))
    mock_remove.assert_called_once_with(repo, ws)


def test_cleanup_lock_only_noop(tmp_path: Path) -> None:
    cleanup_workspace(IsolationLevel.LOCK_ONLY, tmp_path, str(tmp_path))
    # no error, no-op


@patch("maggy.orchestrator.worktree.create_worktree")
def test_provision_with_config_override(mock_create, tmp_path: Path) -> None:
    mock_create.return_value = tmp_path / "wt"
    result = provision_workspace(
        IsolationLevel.WORKTREE, tmp_path / "repo", "chat-abc", tmp_path,
    )
    assert result == str(tmp_path / "wt")
    call_args = mock_create.call_args
    assert call_args.args[1] == "chat-abc"
