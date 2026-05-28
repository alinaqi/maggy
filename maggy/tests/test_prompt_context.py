"""Tests for context layer — project-specific prompt sections."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello(): pass\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "CLAUDE.md").write_text("# Rules\n\nUse pytest.\n")
    git = tmp_path / ".git"
    git.mkdir()
    return tmp_path


class TestFileTreeSection:
    def test_includes_directories(self, project_dir):
        from maggy.prompt.context_layer import file_tree_section
        s = file_tree_section(str(project_dir))
        assert "src/" in s.content

    def test_respects_max_lines(self, project_dir):
        from maggy.prompt.context_layer import file_tree_section
        s = file_tree_section(str(project_dir), max_lines=5)
        lines = s.content.strip().split("\n")
        assert len(lines) <= 10  # includes ``` markers

    def test_layer_is_context(self, project_dir):
        from maggy.prompt.context_layer import file_tree_section
        s = file_tree_section(str(project_dir))
        assert s.layer == "context"


class TestGitStateSection:
    def test_returns_empty_for_non_git(self, tmp_path):
        from maggy.prompt.context_layer import git_state_section
        s = git_state_section(str(tmp_path))
        assert s.content == ""

    def test_layer_is_context(self, tmp_path):
        from maggy.prompt.context_layer import git_state_section
        s = git_state_section(str(tmp_path))
        assert s.layer == "context"


class TestTechStackSection:
    def test_detects_python(self, project_dir):
        from maggy.prompt.context_layer import tech_stack_section
        s = tech_stack_section(str(project_dir))
        assert "python" in s.content.lower()

    def test_detects_node(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name":"app"}')
        from maggy.prompt.context_layer import tech_stack_section
        s = tech_stack_section(str(tmp_path))
        assert "node" in s.content.lower() or "javascript" in s.content.lower()

    def test_empty_for_no_manifests(self, tmp_path):
        from maggy.prompt.context_layer import tech_stack_section
        s = tech_stack_section(str(tmp_path))
        assert s.content == ""


class TestClaudeMdSection:
    def test_includes_content(self, project_dir):
        from maggy.prompt.context_layer import claude_md_section
        s = claude_md_section(str(project_dir))
        assert "pytest" in s.content

    def test_empty_when_missing(self, tmp_path):
        from maggy.prompt.context_layer import claude_md_section
        s = claude_md_section(str(tmp_path))
        assert s.content == ""

    def test_truncates_large(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("x" * 10_000)
        from maggy.prompt.context_layer import claude_md_section
        s = claude_md_section(str(tmp_path), max_chars=500)
        assert len(s.content) < 600


class TestModeSection:
    def test_includes_mode_name(self):
        from maggy.prompt.context_layer import mode_section
        from maggy.prompt.modes import DetectedMode, Mode
        dm = DetectedMode(Mode.PROJECT, 0.9, ["pyproject.toml"])
        s = mode_section(dm)
        assert "project" in s.content.lower()
