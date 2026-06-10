"""Tests for chat grounding — context enrichment for LLM responses."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello(): pass\n")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_hello(): pass\n")
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Key Commands\n```bash\npytest\n```\n")
    (tmp_path / ".gitignore").write_text("__pycache__\n")
    return tmp_path


class TestLoadClaudeMd:
    def test_returns_content_when_present(self, project_dir):
        from maggy.services.chat_grounding import load_claude_md
        result = load_claude_md(str(project_dir))
        assert "Key Commands" in result
        assert "pytest" in result

    def test_returns_empty_when_missing(self, tmp_path):
        from maggy.services.chat_grounding import load_claude_md
        assert load_claude_md(str(tmp_path)) == ""

    def test_truncates_large_files(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("x" * 10_000)
        from maggy.services.chat_grounding import load_claude_md
        result = load_claude_md(str(tmp_path), max_chars=500)
        assert len(result) <= 520


class TestBuildFileTree:
    def test_includes_top_level_dirs(self, project_dir):
        from maggy.services.chat_grounding import build_file_tree
        tree = build_file_tree(str(project_dir))
        assert "src/" in tree
        assert "tests/" in tree

    def test_includes_files(self, project_dir):
        from maggy.services.chat_grounding import build_file_tree
        tree = build_file_tree(str(project_dir))
        assert "main.py" in tree
        assert "CLAUDE.md" in tree

    def test_respects_max_depth(self, project_dir):
        deep = project_dir / "src" / "deep" / "nested"
        deep.mkdir(parents=True)
        (deep / "file.py").write_text("")
        from maggy.services.chat_grounding import build_file_tree
        tree = build_file_tree(str(project_dir), max_depth=1)
        assert "src/" in tree
        assert "nested" not in tree

    def test_skips_hidden_and_generated(self, project_dir):
        (project_dir / ".git").mkdir()
        (project_dir / "node_modules").mkdir()
        (project_dir / "__pycache__").mkdir()
        from maggy.services.chat_grounding import build_file_tree
        tree = build_file_tree(str(project_dir))
        assert ".git/" not in tree
        assert "node_modules/" not in tree
        assert "__pycache__/" not in tree


class TestGroundingInstructions:
    def test_covers_code_verification(self):
        from maggy.services.chat_grounding import grounding_instructions
        text = grounding_instructions()
        assert "verify" in text.lower() or "read" in text.lower()

    def test_covers_research_and_planning(self):
        from maggy.services.chat_grounding import grounding_instructions
        text = grounding_instructions()
        assert "research" in text.lower() or "plan" in text.lower()

    def test_covers_tool_usage(self):
        from maggy.services.chat_grounding import grounding_instructions
        text = grounding_instructions()
        assert "grep" in text.lower() or "shell" in text.lower()

    def test_covers_non_code_tasks(self):
        from maggy.services.chat_grounding import grounding_instructions
        text = grounding_instructions()
        assert "brainstorm" in text.lower() or "discuss" in text.lower() or "question" in text.lower()


class TestBuildEnrichedPrompt:
    def test_includes_grounding(self, project_dir):
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(project_dir), "test-project")
        assert "verify" in prompt.lower() or "shell" in prompt.lower()

    def test_includes_claude_md(self, project_dir):
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(project_dir), "test-project")
        assert "Key Commands" in prompt

    def test_includes_file_tree(self, project_dir):
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(project_dir), "test-project")
        assert "src/" in prompt

    def test_includes_project_name(self, project_dir):
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(project_dir), "my-app")
        assert "my-app" in prompt

    def test_stays_under_size_limit(self, project_dir):
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(project_dir), "test")
        assert len(prompt) < 8000

    def test_works_without_claude_md(self, tmp_path):
        (tmp_path / "index.js").write_text("console.log('hi')")
        from maggy.services.chat_grounding import build_enriched_prompt
        prompt = build_enriched_prompt(str(tmp_path), "new-project")
        assert "new-project" in prompt
        assert "index.js" in prompt
