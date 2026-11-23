"""Read instruction includes and skills from the Maggy source tree.

Includes (e.g. `rules/tdd.md`) and skills (`skills/<name>/SKILL.md`) resolve
against EmitterSources.root: the Maggy repo by default, or MAGGY_HARNESS_SOURCES.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from maggy.harness.emitters.base import EmitterSources
from maggy.harness.errors import HarnessConfigError
from maggy.harness.schema import HarnessProfile

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PROFILE = "<harness profile>"


def default_sources() -> EmitterSources:
    override = os.environ.get("MAGGY_HARNESS_SOURCES")
    return EmitterSources(root=Path(override) if override else Path(__file__).resolve().parents[4])


def safe_name(key: str, name: str) -> str:
    """A skill or hook name usable as a path segment and in a shell command."""
    if not _SAFE_NAME.match(name) or ".." in name:
        raise HarnessConfigError(_PROFILE, [f"{key}: unsafe name {name!r} (use letters, digits, - _ .)"])
    return name


def _resolve(sources: EmitterSources, include: str) -> Path:
    root = sources.root.resolve()
    path = (root / include).resolve()
    if not path.is_relative_to(root):
        raise HarnessConfigError(_PROFILE, [f"instructions.include: {include} is outside {root}"])
    if not path.is_file():
        raise HarnessConfigError(_PROFILE, [f"instructions.include: {include} not found under {root}"])
    return path


def instructions_body(sources: EmitterSources, profile: HarnessProfile) -> str:
    """The shared AGENTS.md block: every include, in order ('' when none)."""
    texts = [_resolve(sources, inc).read_text(encoding="utf-8").strip()
             for inc in profile.instructions.include]
    return "\n\n".join(texts)


def skill_source(sources: EmitterSources, name: str) -> str:
    path = sources.root / "skills" / safe_name("skills", name) / "SKILL.md"
    if not path.is_file():
        raise HarnessConfigError(_PROFILE, [f"skills: no SKILL.md for {name!r} under {path.parent}"])
    return path.read_text(encoding="utf-8")
