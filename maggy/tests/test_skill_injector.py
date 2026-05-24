"""Tests for skill injection into chat prompts."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.skills.injector import build_skill_context, match_skills
from maggy.skills.models import Skill, SkillMetadata
from maggy.skills.registry import SkillRegistry


SKILL_TEMPLATE = """\
---
name: {name}
description: {desc}
when-to-use: {when}
effort: medium
paths: {paths}
---

# {name}

{content}
"""


def _make_skill(base: Path, name: str, paths: str = '[]', content: str = "Rules here.") -> None:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    text = SKILL_TEMPLATE.format(
        name=name, desc=f"{name} skill", when=f"When using {name}",
        paths=paths, content=content,
    )
    (d / "SKILL.md").write_text(text)


@pytest.fixture()
def registry(tmp_path: Path) -> SkillRegistry:
    g = tmp_path / "global"
    g.mkdir()
    _make_skill(g, "base", "[]", "TDD first. Max 20 lines.")
    _make_skill(g, "python", '["**/*.py", "pyproject.toml"]', "Use ruff. Type hints.")
    _make_skill(g, "typescript", '["**/*.ts", "**/*.tsx"]', "Use strict mode.")
    _make_skill(g, "security", "[]", "No secrets in code.")
    reg = SkillRegistry(global_dir=g)
    reg.load_global()
    return reg


class TestMatchSkills:
    def test_base_always_included(self, registry: SkillRegistry):
        skills = registry.resolve()
        matched = match_skills(skills, "/tmp/project")
        names = [s.metadata.name for s in matched]
        assert "base" in names
        assert "security" in names

    def test_python_matched_by_file(self, registry: SkillRegistry, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "main.py").write_text("print('hi')")
        skills = registry.resolve()
        matched = match_skills(skills, str(proj))
        names = [s.metadata.name for s in matched]
        assert "python" in names
        assert "typescript" not in names

    def test_no_project_path_returns_all(self, registry: SkillRegistry):
        skills = registry.resolve()
        matched = match_skills(skills, "")
        assert len(matched) == len(skills)


class TestBuildSkillContext:
    def test_builds_context_string(self, registry: SkillRegistry):
        skills = registry.resolve()
        ctx = build_skill_context(skills[:2])
        assert "[Skills]" in ctx
        assert "[/Skills]" in ctx

    def test_empty_skills(self):
        ctx = build_skill_context([])
        assert ctx == ""

    def test_content_included(self, registry: SkillRegistry):
        skills = registry.resolve()
        ctx = build_skill_context(skills)
        assert "TDD first" in ctx
        assert "No secrets" in ctx

    def test_max_token_budget(self, registry: SkillRegistry):
        skills = registry.resolve()
        ctx = build_skill_context(skills, max_chars=50)
        assert len(ctx) <= 200
