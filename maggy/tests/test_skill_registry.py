"""Tests for SkillRegistry — global + project skill merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.skills.registry import SkillRegistry


GLOBAL_SKILL = """\
---
name: {name}
description: Global {name}
when-to-use: Always
effort: medium
---

# {name}

Global content for {name}.
"""

PROJECT_SKILL = """\
---
name: {name}
description: Project {name}
when-to-use: In this project
effort: high
---

# {name}

Project-specific content for {name}.
"""


def _make_skill(base: Path, name: str, template: str) -> None:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(template.format(name=name))


@pytest.fixture()
def global_dir(tmp_path: Path) -> Path:
    d = tmp_path / "global"
    d.mkdir()
    _make_skill(d, "base", GLOBAL_SKILL)
    _make_skill(d, "python", GLOBAL_SKILL)
    _make_skill(d, "security", GLOBAL_SKILL)
    return d


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "project" / ".claude" / "skills"
    d.mkdir(parents=True)
    _make_skill(d, "python", PROJECT_SKILL)
    _make_skill(d, "custom-api", PROJECT_SKILL)
    return tmp_path / "project"


class TestLoadGlobal:
    def test_loads_all_global(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        count = reg.load_global()
        assert count == 3

    def test_list_global(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        skills = reg.list_global()
        names = {s.metadata.name for s in skills}
        assert names == {"base", "python", "security"}

    def test_all_marked_global(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        for s in reg.list_global():
            assert s.source == "global"


class TestLoadProject:
    def test_loads_project_skills(self, global_dir: Path, project_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        count = reg.load_project("proj", str(project_dir))
        assert count == 2

    def test_list_project(self, global_dir: Path, project_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skills = reg.list_project("proj")
        names = {s.metadata.name for s in skills}
        assert names == {"python", "custom-api"}

    def test_no_project_dir(self, global_dir: Path, tmp_path: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        count = reg.load_project("empty", str(tmp_path / "nope"))
        assert count == 0


class TestResolve:
    def test_global_only(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        skills = reg.resolve()
        assert len(skills) == 3

    def test_merge_with_override(self, global_dir: Path, project_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skills = reg.resolve("proj")
        names = [s.metadata.name for s in skills]
        assert len(skills) == 4
        assert "custom-api" in names

    def test_override_uses_project_content(self, global_dir, project_dir):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skills = reg.resolve("proj")
        python = next(s for s in skills if s.metadata.name == "python")
        assert python.source == "project"
        assert python.is_override is True
        assert "Project-specific" in python.content

    def test_non_overridden_stays_global(self, global_dir, project_dir):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skills = reg.resolve("proj")
        base = next(s for s in skills if s.metadata.name == "base")
        assert base.source == "global"
        assert base.is_override is False

    def test_sorted_by_name(self, global_dir: Path, project_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skills = reg.resolve("proj")
        names = [s.metadata.name for s in skills]
        assert names == sorted(names)


class TestGet:
    def test_get_global(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        skill = reg.get("base")
        assert skill is not None
        assert skill.metadata.name == "base"

    def test_get_project_override(self, global_dir, project_dir):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        skill = reg.get("python", "proj")
        assert skill is not None
        assert skill.source == "project"

    def test_get_missing(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        assert reg.get("nonexistent") is None


class TestReload:
    def test_reload_picks_up_new(self, global_dir: Path):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        assert len(reg.list_global()) == 3
        _make_skill(global_dir, "new-skill", GLOBAL_SKILL)
        reg.reload()
        assert len(reg.list_global()) == 4

    def test_reload_project(self, global_dir, project_dir):
        reg = SkillRegistry(global_dir=global_dir)
        reg.load_global()
        reg.load_project("proj", str(project_dir))
        assert len(reg.resolve("proj")) == 4
        count = reg.reload("proj")
        assert count > 0
