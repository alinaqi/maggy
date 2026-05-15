"""Tests for merge module — patch generation and apply."""
from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from maggy.orchestrator.merge import (
    merge_changes,
    _apply_patch,
    _generate_patch,
)


@patch("maggy.orchestrator.merge._run_git")
def test_generate_patch_calls_diff(mock_git, tmp_path: Path) -> None:
    mock_git.return_value = CompletedProcess(
        [], 0, stdout=b"diff --git a/f.py b/f.py\n"
    )
    result = _generate_patch(tmp_path / "ws")
    assert result == b"diff --git a/f.py b/f.py\n"
    cmd = mock_git.call_args.args[0]
    assert "diff" in cmd


@patch("maggy.orchestrator.merge._run_git")
def test_generate_patch_empty(mock_git, tmp_path: Path) -> None:
    mock_git.return_value = CompletedProcess([], 0, stdout=b"")
    result = _generate_patch(tmp_path / "ws")
    assert result == b""


@patch("maggy.orchestrator.merge._run_git")
def test_apply_patch_success(mock_git, tmp_path: Path) -> None:
    mock_git.return_value = CompletedProcess([], 0)
    ok = _apply_patch(tmp_path / "repo", b"diff content")
    assert ok is True


@patch("maggy.orchestrator.merge._run_git")
def test_apply_patch_failure(mock_git, tmp_path: Path) -> None:
    mock_git.return_value = CompletedProcess([], 1, stderr=b"conflict")
    ok = _apply_patch(tmp_path / "repo", b"diff content")
    assert ok is False


@patch("maggy.orchestrator.merge._apply_patch")
@patch("maggy.orchestrator.merge._generate_patch")
def test_merge_changes_success(mock_gen, mock_apply, tmp_path: Path) -> None:
    mock_gen.return_value = b"some diff"
    mock_apply.return_value = True
    ok = merge_changes(tmp_path / "repo", tmp_path / "ws")
    assert ok is True
    mock_apply.assert_called_once()


@patch("maggy.orchestrator.merge._apply_patch")
@patch("maggy.orchestrator.merge._generate_patch")
def test_merge_changes_no_diff(mock_gen, mock_apply, tmp_path: Path) -> None:
    mock_gen.return_value = b""
    ok = merge_changes(tmp_path / "repo", tmp_path / "ws")
    assert ok is True
    mock_apply.assert_not_called()


@patch("maggy.orchestrator.merge._apply_patch")
@patch("maggy.orchestrator.merge._generate_patch")
def test_merge_changes_conflict(mock_gen, mock_apply, tmp_path: Path) -> None:
    mock_gen.return_value = b"diff"
    mock_apply.return_value = False
    ok = merge_changes(tmp_path / "repo", tmp_path / "ws")
    assert ok is False
