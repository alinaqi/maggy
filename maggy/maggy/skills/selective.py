"""Selective skill loading — index for prompts, full on demand."""

from __future__ import annotations

from maggy.skills.models import Skill

_MAX_MATCH = 3


def build_skill_index(skills: list[Skill]) -> str:
    if not skills:
        return ""
    lines = ["## Available Skills"]
    for s in skills:
        name = s.metadata.name
        desc = s.metadata.description
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def match_for_task(
    task: str, skills: list[Skill],
) -> list[Skill]:
    if not task.strip():
        return []
    words = task.lower().split()
    scored: list[tuple[float, Skill]] = []
    for skill in skills:
        score = _relevance_score(words, skill)
        if score > 0:
            scored.append((score, skill))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:_MAX_MATCH]]


def _relevance_score(
    task_words: list[str], skill: Skill,
) -> float:
    name = skill.metadata.name.lower()
    desc = skill.metadata.description.lower()
    when = skill.metadata.when_to_use.lower()
    searchable = f"{name} {desc} {when}"
    score = 0.0
    for word in task_words:
        if len(word) < 3:
            continue
        if word in name:
            score += 3.0
        elif word in desc:
            score += 2.0
        elif word in when:
            score += 1.5
        elif word in searchable:
            score += 1.0
    return score


def build_selective_context(
    skills: list[Skill], max_chars: int = 8000,
) -> str:
    if not skills:
        return ""
    parts: list[str] = []
    total = 0
    for skill in skills:
        entry = f"## {skill.metadata.name}\n{skill.content.strip()}\n"
        if total + len(entry) > max_chars:
            entry = entry[:max_chars - total] + "\n...(truncated)"
            parts.append(entry)
            break
        parts.append(entry)
        total += len(entry)
    if not parts:
        return ""
    return f"[Skills]\n{''.join(parts)}[/Skills]"
