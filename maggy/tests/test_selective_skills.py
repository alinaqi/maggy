"""Tests for selective skill loading — index vs full content."""

from __future__ import annotations

import pytest

from maggy.skills.models import Skill, SkillMetadata


def _make_skill(name: str, desc: str, content: str) -> Skill:
    return Skill(
        metadata=SkillMetadata(name=name, description=desc),
        content=content,
        source="test",
        source_path=f"/tmp/{name}/SKILL.md",
    )


class TestSkillIndex:
    def test_builds_index_from_skills(self):
        from maggy.skills.selective import build_skill_index
        skills = [
            _make_skill("python", "Python conventions", "Full body..."),
            _make_skill("react", "React patterns", "Full body..."),
        ]
        index = build_skill_index(skills)
        assert "python" in index.lower()
        assert "react" in index.lower()
        assert "Python conventions" in index
        assert "Full body" not in index

    def test_empty_skills_returns_empty(self):
        from maggy.skills.selective import build_skill_index
        assert build_skill_index([]) == ""

    def test_index_is_concise(self):
        from maggy.skills.selective import build_skill_index
        skills = [
            _make_skill(f"skill-{i}", f"Desc {i}", "x" * 5000)
            for i in range(10)
        ]
        index = build_skill_index(skills)
        assert len(index) < 2000


class TestMatchForTask:
    def test_matches_python_task(self):
        from maggy.skills.selective import match_for_task
        skills = [
            _make_skill("python", "Python coding conventions", "..."),
            _make_skill("react", "React component patterns", "..."),
            _make_skill("security", "Security best practices", "..."),
        ]
        matched = match_for_task("fix the Python test suite", skills)
        names = [s.metadata.name for s in matched]
        assert "python" in names

    def test_matches_security_task(self):
        from maggy.skills.selective import match_for_task
        skills = [
            _make_skill("python", "Python coding conventions", "..."),
            _make_skill("security", "Security and auth patterns", "..."),
        ]
        matched = match_for_task(
            "review auth middleware for vulnerabilities", skills,
        )
        names = [s.metadata.name for s in matched]
        assert "security" in names

    def test_returns_max_3(self):
        from maggy.skills.selective import match_for_task
        skills = [
            _make_skill(f"s{i}", f"Skill {i}", "...") for i in range(10)
        ]
        matched = match_for_task("do everything", skills)
        assert len(matched) <= 3

    def test_empty_task_returns_empty(self):
        from maggy.skills.selective import match_for_task
        skills = [_make_skill("a", "desc", "body")]
        matched = match_for_task("", skills)
        assert matched == []


class TestBuildSelectiveContext:
    def test_builds_context_from_matched(self):
        from maggy.skills.selective import build_selective_context
        skills = [
            _make_skill(
                "python", "Python",
                "Use type hints on all functions.",
            ),
        ]
        ctx = build_selective_context(skills)
        assert "type hints" in ctx
        assert "python" in ctx.lower()

    def test_respects_max_chars(self):
        from maggy.skills.selective import build_selective_context
        skills = [_make_skill("big", "Huge", "x" * 10000)]
        ctx = build_selective_context(skills, max_chars=500)
        assert len(ctx) <= 600
