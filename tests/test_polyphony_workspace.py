"""Tests for Polyphony workspace manager (§6)."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from polyphony.workspace import (
    workspace_path,
    create_workspace,
    cleanup_workspace,
    list_workspaces,
)


class TestWorkspacePath:
    def test_creates_path(self, tmp_path):
        p = workspace_path(tmp_path, "TASK-1", 1)
        assert "TASK-1" in str(p)
        assert "1" in str(p)

    def test_sanitizes_id(self, tmp_path):
        p = workspace_path(tmp_path, "owner/repo#42", 1)
        # No slashes in directory name
        assert "/" not in p.name


class TestCreateWorkspace:
    @patch("polyphony.workspace._run_git")
    def test_clones_repo(self, mock_git, tmp_path):
        mock_git.return_value = MagicMock(returncode=0)
        ws = create_workspace(
            base_dir=tmp_path,
            task_id="T-1",
            attempt=1,
            repo_url="https://github.com/o/r.git",
            ref="main",
        )
        assert ws.exists()
        assert mock_git.called

    @patch("polyphony.workspace._run_git")
    def test_checks_out_branch(self, mock_git, tmp_path):
        mock_git.return_value = MagicMock(returncode=0)
        create_workspace(
            base_dir=tmp_path,
            task_id="T-2",
            attempt=1,
            repo_url="https://github.com/o/r.git",
            ref="feature/auth",
        )
        calls = [str(c) for c in mock_git.call_args_list]
        assert any("checkout" in c for c in calls)

    @patch("polyphony.workspace._run_git")
    def test_uses_mirror_when_available(self, mock_git, tmp_path):
        mock_git.return_value = MagicMock(returncode=0)
        mirror = tmp_path / "mirror" / "repo.git"
        mirror.mkdir(parents=True)
        create_workspace(
            base_dir=tmp_path,
            task_id="T-3",
            attempt=1,
            repo_url="https://github.com/o/r.git",
            ref="main",
            mirror_path=mirror,
        )
        calls = [str(c) for c in mock_git.call_args_list]
        assert any("dissociate" in c for c in calls)


class TestCleanupWorkspace:
    def test_removes_directory(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "file.txt").write_text("x")
        cleanup_workspace(ws)
        assert not ws.exists()

    def test_missing_dir_no_error(self, tmp_path):
        cleanup_workspace(tmp_path / "nope")


class TestListWorkspaces:
    def test_lists_dirs(self, tmp_path):
        (tmp_path / "T-1" / "1").mkdir(parents=True)
        (tmp_path / "T-2" / "1").mkdir(parents=True)
        ws = list_workspaces(tmp_path)
        assert len(ws) >= 2

    def test_empty_base(self, tmp_path):
        assert list_workspaces(tmp_path) == []
