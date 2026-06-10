"""Tests for prompt assembly — combines all layers."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main(): pass\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "CLAUDE.md").write_text("# Rules\nUse pytest.\n")
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestPromptAssemblyService:
    def test_assembles_all_layers(self, project_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble(str(project_dir), "demo")
        assert "Maggy" in result
        assert "Capabilities" in result
        assert "src/" in result

    def test_project_mode_includes_full_context(self, project_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble(str(project_dir), "demo")
        assert "project" in result.lower()
        assert "pytest" in result

    def test_bootstrap_mode_minimal_context(self, empty_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble(str(empty_dir), "new-project")
        assert "bootstrap" in result.lower()
        assert "new-project" in result

    def test_stays_under_size_limit(self, project_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble(str(project_dir), "demo")
        assert len(result) < 12000

    def test_fallback_on_error(self, project_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble("/nonexistent/path", "broken")
        assert "Maggy" in result
        assert len(result) > 50

    def test_includes_working_dir(self, project_dir):
        from maggy.prompt.assembly import PromptAssemblyService
        svc = PromptAssemblyService()
        result = svc.assemble(str(project_dir), "demo")
        assert str(project_dir) in result
