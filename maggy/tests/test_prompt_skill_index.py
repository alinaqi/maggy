"""Tests for skill index — compact one-line skill entries in prompt."""

from __future__ import annotations

import pytest

from maggy.skills.models import Skill, SkillMetadata


def _make_skill(
    name: str, desc: str, content: str = "Full body.",
    when: str = "", invocable: bool = False,
) -> Skill:
    return Skill(
        metadata=SkillMetadata(
            name=name, description=desc,
            when_to_use=when, user_invocable=invocable,
        ),
        content=content, source="test", source_path="/tmp/s",
    )


class TestSkillIndexSection:
    def test_produces_prompt_section(self):
        from maggy.prompt.skill_index import skill_index_section
        skills = [_make_skill("python", "Python patterns")]
        s = skill_index_section(skills)
        assert s.layer == "context"
        assert s.id == "skill_index"

    def test_includes_skill_name_and_desc(self):
        from maggy.prompt.skill_index import skill_index_section
        skills = [_make_skill("python", "Python patterns")]
        s = skill_index_section(skills)
        assert "python" in s.content
        assert "Python patterns" in s.content

    def test_multiple_skills_one_line_each(self):
        from maggy.prompt.skill_index import skill_index_section
        skills = [
            _make_skill("python", "Python patterns"),
            _make_skill("react", "React components"),
        ]
        s = skill_index_section(skills)
        assert "python" in s.content
        assert "react" in s.content
        lines = [l for l in s.content.split("\n") if l.startswith("- ")]
        assert len(lines) == 2

    def test_empty_skills_returns_empty_content(self):
        from maggy.prompt.skill_index import skill_index_section
        s = skill_index_section([])
        assert s.content == ""

    def test_marks_invocable_skills(self):
        from maggy.prompt.skill_index import skill_index_section
        skills = [_make_skill("deploy", "Deploy flow", invocable=True)]
        s = skill_index_section(skills)
        assert "invocable" in s.content.lower() or "/" in s.content

    def test_does_not_include_full_body(self):
        from maggy.prompt.skill_index import skill_index_section
        body = "x" * 500
        skills = [_make_skill("big", "Big skill", content=body)]
        s = skill_index_section(skills)
        assert body not in s.content
        assert len(s.content) < 200
