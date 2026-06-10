"""Skill injection — match and format skills for model prompts."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from maggy.skills.models import Skill


def match_skills(
    skills: list[Skill], project_path: str,
) -> list[Skill]:
    """Filter skills relevant to a project by paths: globs."""
    if not project_path or not os.path.isdir(project_path):
        return list(skills)
    project_files = _scan_project_files(project_path)
    matched: list[Skill] = []
    for skill in skills:
        globs = skill.metadata.paths
        if not globs:
            matched.append(skill)
            continue
        if _any_glob_matches(globs, project_files):
            matched.append(skill)
    return matched


def _scan_project_files(project_path: str, limit: int = 500) -> list[str]:
    """Collect relative file paths from project (top 2 levels)."""
    root = Path(project_path)
    files: list[str] = []
    skip = {".git", "node_modules", ".next", "dist", "__pycache__", ".venv"}
    for item in root.iterdir():
        if item.name in skip or item.name.startswith("."):
            continue
        if item.is_file():
            files.append(item.name)
        elif item.is_dir():
            for sub in item.iterdir():
                if sub.is_file():
                    files.append(f"{item.name}/{sub.name}")
                if len(files) >= limit:
                    return files
    return files


def _any_glob_matches(globs: list[str], files: list[str]) -> bool:
    """Check if any file matches any of the glob patterns."""
    for pattern in globs:
        simple = pattern.replace("**/", "")
        for f in files:
            if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(f, simple):
                return True
    return False


def build_skill_context(
    skills: list[Skill], max_chars: int = 8000,
) -> str:
    """Format matched skills into a context block for prompts."""
    if not skills:
        return ""
    parts: list[str] = []
    total = 0
    for skill in skills:
        entry = f"## {skill.metadata.name}\n{skill.content.strip()}\n"
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
    if not parts:
        return ""
    body = "\n".join(parts)
    return f"[Skills]\n{body}[/Skills]"
