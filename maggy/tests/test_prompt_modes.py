"""Tests for mode detection — project vs workspace vs bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Stuff\n")
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestDetectMode:
    def test_detects_project_with_pyproject(self, project_dir):
        from maggy.prompt.modes import detect_mode, Mode
        result = detect_mode(str(project_dir))
        assert result.mode == Mode.PROJECT

    def test_detects_project_with_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name":"test"}')
        (tmp_path / ".git").mkdir()
        from maggy.prompt.modes import detect_mode, Mode
        result = detect_mode(str(tmp_path))
        assert result.mode == Mode.PROJECT

    def test_detects_project_with_claude_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Instructions\n")
        from maggy.prompt.modes import detect_mode, Mode
        result = detect_mode(str(tmp_path))
        assert result.mode == Mode.PROJECT

    def test_detects_workspace_with_git(self, workspace_dir):
        from maggy.prompt.modes import detect_mode, Mode
        result = detect_mode(str(workspace_dir))
        assert result.mode == Mode.WORKSPACE

    def test_detects_bootstrap_default(self, empty_dir):
        from maggy.prompt.modes import detect_mode, Mode
        result = detect_mode(str(empty_dir))
        assert result.mode == Mode.BOOTSTRAP

    def test_confidence_high_for_project(self, project_dir):
        from maggy.prompt.modes import detect_mode
        result = detect_mode(str(project_dir))
        assert result.confidence >= 0.8

    def test_confidence_low_for_bootstrap(self, empty_dir):
        from maggy.prompt.modes import detect_mode
        result = detect_mode(str(empty_dir))
        assert result.confidence <= 0.5

    def test_markers_populated(self, project_dir):
        from maggy.prompt.modes import detect_mode
        result = detect_mode(str(project_dir))
        assert "pyproject.toml" in result.markers
