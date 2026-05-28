"""Skill index — compact one-line entries in prompt, full content on demand."""

from __future__ import annotations

from maggy.prompt.sections import PromptSection
from maggy.skills.models import Skill


def skill_index_section(skills: list[Skill]) -> PromptSection:
    if not skills:
        return PromptSection(
            id="skill_index", layer="context", content="",
        )
    lines: list[str] = []
    for skill in skills:
        meta = skill.metadata
        tag = " [/invocable]" if meta.user_invocable else ""
        lines.append(f"- **{meta.name}**: {meta.description}{tag}")
    content = "## Available Skills\n" + "\n".join(lines)
    return PromptSection(
        id="skill_index", layer="context",
        content=content, priority=8,
    )
