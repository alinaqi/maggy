"""Tests for skill loader — discovery and SKILL.md parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.skills.loader import (
    discover_skills,
    global_skills_dir,
    load_all,
    load_skill,
    parse_skill_md,
    project_skills_dir,
)
from maggy.skills.models import SkillMetadata


SAMPLE_SKILL = """\
---
name: test-skill
description: A test skill
when-to-use: During tests
user-invocable: true
effort: low
paths: [\"**/*.py\"]
---

# Test Skill

Some content here.
"""

MINIMAL_SKILL = """\
---
name: minimal
description: Minimal skill
---

# Minimal
"""


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """Create a temp skills directory with sample skills."""
    s1 = tmp_path / "test-skill"
    s1.mkdir()
    (s1 / "SKILL.md").write_text(SAMPLE_SKILL)

    s2 = tmp_path / "minimal"
    s2.mkdir()
    (s2 / "SKILL.md").write_text(MINIMAL_SKILL)

    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "SKILL.md").write_text(MINIMAL_SKILL)

    return tmp_path


class TestDiscoverSkills:
    def test_finds_skill_dirs(self, skills_dir: Path):
        dirs = discover_skills(skills_dir)
        names = [d.name for d in dirs]
        assert "test-skill" in names
        assert "minimal" in names

    def test_skips_hidden(self, skills_dir: Path):
        dirs = discover_skills(skills_dir)
        names = [d.name for d in dirs]
        assert ".hidden" not in names

    def test_sorted_output(self, skills_dir: Path):
        dirs = discover_skills(skills_dir)
        names = [d.name for d in dirs]
        assert names == sorted(names)

    def test_nonexistent_dir(self, tmp_path: Path):
        dirs = discover_skills(tmp_path / "nope")
        assert dirs == []

    def test_empty_dir(self, tmp_path: Path):
        d = tmp_path / "empty"
        d.mkdir()
        dirs = discover_skills(d)
        assert dirs == []


class TestParseSkillMd:
    def test_parses_frontmatter(self, skills_dir: Path):
        path = skills_dir / "test-skill" / "SKILL.md"
        meta, body = parse_skill_md(path)
        assert meta.name == "test-skill"
        assert meta.description == "A test skill"
        assert meta.when_to_use == "During tests"
        assert meta.user_invocable is True
        assert meta.effort == "low"

    def test_parses_body(self, skills_dir: Path):
        path = skills_dir / "test-skill" / "SKILL.md"
        _, body = parse_skill_md(path)
        assert "# Test Skill" in body
        assert "Some content here." in body

    def test_minimal_skill(self, skills_dir: Path):
        path = skills_dir / "minimal" / "SKILL.md"
        meta, body = parse_skill_md(path)
        assert meta.name == "minimal"
        assert meta.when_to_use == ""
        assert "# Minimal" in body

    def test_no_frontmatter(self, tmp_path: Path):
        path = tmp_path / "SKILL.md"
        path.write_text("# Just content\nNo frontmatter.")
        meta, body = parse_skill_md(path)
        assert meta.name == ""
        assert meta.description == ""

    def test_missing_file(self, tmp_path: Path):
        path = tmp_path / "missing" / "SKILL.md"
        meta, body = parse_skill_md(path)
        assert meta.name == ""
        assert body == ""


class TestLoadSkill:
    def test_loads_skill(self, skills_dir: Path):
        skill = load_skill(skills_dir / "test-skill", "global")
        assert skill is not None
        assert skill.metadata.name == "test-skill"
        assert skill.source == "global"
        assert "SKILL.md" in skill.source_path

    def test_missing_skill_md(self, tmp_path: Path):
        d = tmp_path / "no-skill"
        d.mkdir()
        skill = load_skill(d, "project")
        assert skill is None


class TestLoadAll:
    def test_loads_all(self, skills_dir: Path):
        skills = load_all(skills_dir, "global")
        assert len(skills) == 2
        names = {s.metadata.name for s in skills}
        assert "test-skill" in names
        assert "minimal" in names

    def test_all_have_source(self, skills_dir: Path):
        skills = load_all(skills_dir, "project")
        for s in skills:
            assert s.source == "project"


class TestPaths:
    def test_global_skills_dir(self):
        d = global_skills_dir()
        assert d == Path.home() / ".claude" / "skills"

    def test_project_skills_dir(self):
        d = project_skills_dir("/tmp/my-project")
        assert d == Path("/tmp/my-project/.claude/skills")
