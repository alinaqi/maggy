"""SkillRegistry — load, merge, and query skills."""

from __future__ import annotations

from pathlib import Path

from maggy.skills.loader import (
    global_skills_dir,
    load_all,
    project_skills_dir,
)
from maggy.skills.models import Skill


class SkillRegistry:
    """Load global + project skills with layered inheritance."""

    def __init__(self, global_dir: Path | None = None):
        self._global_dir = global_dir or global_skills_dir()
        self._global: dict[str, Skill] = {}
        self._projects: dict[str, dict[str, Skill]] = {}
        self._project_paths: dict[str, str] = {}

    def load_global(self) -> int:
        self._global.clear()
        for skill in load_all(self._global_dir, "global"):
            self._global[skill.metadata.name] = skill
        return len(self._global)

    def load_project(self, project_key: str, project_path: str) -> int:
        self._project_paths[project_key] = project_path
        skills_dir = project_skills_dir(project_path)
        loaded: dict[str, Skill] = {}
        for skill in load_all(skills_dir, "project"):
            loaded[skill.metadata.name] = skill
        self._projects[project_key] = loaded
        return len(loaded)

    def resolve(self, project_key: str | None = None) -> list[Skill]:
        merged: dict[str, Skill] = {}
        for name, skill in self._global.items():
            merged[name] = skill
        if project_key and project_key in self._projects:
            for name, skill in self._projects[project_key].items():
                is_override = name in merged
                merged[name] = Skill(
                    metadata=skill.metadata,
                    content=skill.content,
                    source=skill.source,
                    source_path=skill.source_path,
                    is_override=is_override,
                )
        return sorted(merged.values(), key=lambda s: s.metadata.name)

    def get(self, name: str, project_key: str | None = None) -> Skill | None:
        if project_key and project_key in self._projects:
            proj = self._projects[project_key].get(name)
            if proj:
                return proj
        return self._global.get(name)

    def list_global(self) -> list[Skill]:
        return sorted(self._global.values(), key=lambda s: s.metadata.name)

    def list_project(self, project_key: str) -> list[Skill]:
        proj = self._projects.get(project_key, {})
        return sorted(proj.values(), key=lambda s: s.metadata.name)

    def reload(self, project_key: str | None = None) -> int:
        count = self.load_global()
        if project_key and project_key in self._project_paths:
            count += self.load_project(
                project_key, self._project_paths[project_key],
            )
        return count
