"""Managed skill copies: <skills_dir>/<name>/SKILL.md, whole-file.

A copy carries MARKER right after its frontmatter (frontmatter must stay
first). Only marked files are updated or deleted (see copies.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.emitters.base import EmitterSources
from maggy.harness.emitters.copies import CopyKind, plan_copies
from maggy.harness.emitters.sources import skill_source

MARKER = "<!-- maggy:managed-skill -->"
SKILL = CopyKind(marker=MARKER, rid="skill", label="skill")
_FRONTMATTER = re.compile(r"\A---\r?\n.*?^---[ \t]*\r?\n", re.S | re.M)
Env = tuple[EmitterSources, HarnessContext]


def managed_text(source: str) -> str:
    found = _FRONTMATTER.match(source)
    cut = found.end() if found else 0
    return f"{source[:cut]}{MARKER}\n{source[cut:]}"


class SkillSet(NamedTuple):
    """Profile skill names (from the Maggy sources) plus extra name -> SKILL.md texts
    (e.g. AWG's skill), all copied into `dir`."""

    names: list[str]
    dir: Path
    extra: dict[str, str] = {}


def plan_skills(skills: SkillSet, env: Env) -> list[FileChange]:
    sources, ctx = env
    texts = {**skills.extra, **{n: skill_source(sources, n) for n in skills.names}}
    skills_dir = skills.dir
    wanted = {skills_dir / n / "SKILL.md": managed_text(text) for n, text in texts.items()}
    stale = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []
    return plan_copies(wanted, stale, (ctx, SKILL))
