"""Tests for project bootstrap detector."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.services.project_bootstrap import (
    CliStatus,
    GitState,
    ProjectStatus,
    detect_cli_inventory,
    detect_cortex_state,
    detect_dev_tools,
    detect_git_state,
    detect_project_stack,
    run_bootstrap,
)


class TestCliInventory:
    def test_returns_cli_status_list(self):
        result = detect_cli_inventory()
        assert isinstance(result, list)
        assert all(isinstance(c, CliStatus) for c in result)

    def test_includes_known_clis(self):
        result = detect_cli_inventory()
        names = [c.name for c in result]
        assert "claude" in names

    def test_each_has_installed_flag(self):
        result = detect_cli_inventory()
        for cli in result:
            assert isinstance(cli.installed, bool)
            assert isinstance(cli.name, str)


class TestDevTools:
    def test_returns_cli_status_list(self):
        result = detect_dev_tools()
        assert isinstance(result, list)
        assert all(isinstance(c, CliStatus) for c in result)

    def test_includes_core_tools(self):
        result = detect_dev_tools()
        names = [c.name for c in result]
        assert "git" in names
        assert "gh" in names

    def test_git_is_installed(self):
        result = detect_dev_tools()
        git = next(c for c in result if c.name == "git")
        assert git.installed is True


class TestProjectStack:
    def test_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')")
        stack = detect_project_stack(str(tmp_path))
        assert stack["type"] == "python"
        assert "pyproject.toml" in stack["markers"]

    def test_node_project(self, tmp_path: Path):
        (tmp_path / "package.json").write_text('{"name":"test"}')
        stack = detect_project_stack(str(tmp_path))
        assert stack["type"] == "node"

    def test_unknown_project(self, tmp_path: Path):
        stack = detect_project_stack(str(tmp_path))
        assert stack["type"] == "unknown"

    def test_detects_test_runner(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='t'\n[tool.pytest]\n"
        )
        stack = detect_project_stack(str(tmp_path))
        assert "pytest" in stack.get("test_runner", "")

    def test_nonexistent_dir(self):
        stack = detect_project_stack("/nonexistent")
        assert stack["type"] == "unknown"


class TestGitState:
    def test_no_git_dir(self, tmp_path: Path):
        state = detect_git_state(str(tmp_path))
        assert state.is_repo is False
        assert state.branch == ""

    def test_git_repo_detected(self, tmp_path: Path):
        subprocess.run(
            ["git", "init"], cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path, capture_output=True,
            env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                 "PATH": "/usr/bin:/usr/local/bin"},
        )
        state = detect_git_state(str(tmp_path))
        assert state.is_repo is True
        assert state.branch != ""

    def test_uncommitted_changes(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        (tmp_path / "file.txt").write_text("hello")
        state = detect_git_state(str(tmp_path))
        assert state.has_uncommitted is True

    def test_nonexistent_dir(self):
        state = detect_git_state("/nonexistent/path")
        assert state.is_repo is False


class TestCortexState:
    def test_no_cortex(self, tmp_path: Path):
        result = detect_cortex_state(str(tmp_path))
        assert result["exists"] is False

    def test_cortex_exists(self, tmp_path: Path):
        (tmp_path / ".cortex").mkdir()
        (tmp_path / ".cortex" / "graph.db").write_text("")
        result = detect_cortex_state(str(tmp_path))
        assert result["exists"] is True

    def test_nonexistent_dir(self):
        result = detect_cortex_state("/nonexistent")
        assert result["exists"] is False


class TestRunBootstrap:
    def test_returns_project_status(self, tmp_path: Path):
        status = run_bootstrap(str(tmp_path))
        assert isinstance(status, ProjectStatus)
        assert isinstance(status.clis, list)
        assert isinstance(status.git, GitState)

    def test_never_raises(self):
        status = run_bootstrap("/nonexistent/path/that/wont/exist")
        assert isinstance(status, ProjectStatus)

    def test_has_cortex_field(self, tmp_path: Path):
        status = run_bootstrap(str(tmp_path))
        assert "exists" in status.cortex

    def test_has_tools_and_stack(self, tmp_path: Path):
        status = run_bootstrap(str(tmp_path))
        d = status.to_dict()
        assert "tools" in d
        assert "stack" in d
        assert isinstance(d["tools"], list)
        assert isinstance(d["stack"], dict)

    def test_to_dict(self, tmp_path: Path):
        status = run_bootstrap(str(tmp_path))
        d = status.to_dict()
        assert "clis" in d
        assert "git" in d
        assert "cortex" in d
        assert isinstance(d["clis"], list)
