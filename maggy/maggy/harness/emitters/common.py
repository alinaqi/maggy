"""Shared emitter plumbing: managed-file specs to planned changes."""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.base import EmitterSources, Scope
from maggy.harness.emitters.skills import SkillSet, plan_skills
from maggy.harness.plan import plan_files


def markdown(path: Path, regions: dict[str, str]) -> ManagedFile:
    return ManagedFile(path=path, format="markdown", regions=regions)


def run_plan(files: list[ManagedFile], skills: SkillSet,
             env: tuple[EmitterSources, Scope]) -> list[FileChange]:
    """Plan managed files, then skill copies; nothing is written."""
    sources, scope = env
    ctx = scope.context()
    return plan_files(files, ctx) + plan_skills(skills, (sources, ctx))
