"""Shared emitter plumbing: managed-file specs to planned changes."""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.base import EmitterSources, Scope
from maggy.harness.emitters.skills import plan_skills
from maggy.harness.plan import plan_files


def markdown(path: Path, regions: dict[str, str]) -> ManagedFile:
    return ManagedFile(path=path, format="markdown", regions=regions)


def run_plan(files: list[ManagedFile], skills: tuple[list[str], Path],
             env: tuple[EmitterSources, Scope]) -> list[FileChange]:
    """Plan managed files, then skill copies; nothing is written."""
    sources, scope = env
    ctx = scope.context()
    names, skills_dir = skills
    return plan_files(files, ctx) + plan_skills(names, skills_dir, (sources, ctx))
