"""Skill discovery and SKILL.md parsing."""

from __future__ import annotations

import re
from pathlib import Path

from maggy.skills.models import Skill, SkillMetadata

_FM_FIELD_RE = re.compile(r"^(\w[\w-]*)\s*:\s*(.*)")


def global_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def project_skills_dir(project_path: str) -> Path:
    return Path(project_path) / ".claude" / "skills"


def discover_skills(skills_dir: Path) -> list[Path]:
    if not skills_dir.is_dir():
        return []
    return sorted(
        d for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def _parse_frontmatter(content: str) -> tuple[dict[str, str], int]:
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields: dict[str, str] = {}
    end_line = 0
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            end_line = i
            break
        match = _FM_FIELD_RE.match(line)
        if match:
            key = match.group(1).strip()
            val = match.group(2).strip()
            if len(val) >= 2 and val[0] in ("\"", "'") and val[-1] == val[0]:
                val = val[1:-1]
            fields[key] = val
    return fields, end_line


def _parse_paths(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
    return [raw] if raw else []


def _parse_bool(raw: str) -> bool:
    return raw.lower() in ("true", "yes", "1")


def parse_skill_md(skill_path: Path) -> tuple[SkillMetadata, str]:
    if not skill_path.exists():
        return SkillMetadata(name="", description=""), ""
    content = skill_path.read_text(encoding="utf-8")
    fields, end_line = _parse_frontmatter(content)
    lines = content.split("\n")
    body = "\n".join(lines[end_line:]).strip() if end_line else content
    meta = SkillMetadata(
        name=fields.get("name", ""),
        description=fields.get("description", ""),
        when_to_use=fields.get("when-to-use", ""),
        user_invocable=_parse_bool(fields.get("user-invocable", "false")),
        paths=_parse_paths(fields.get("paths", "")),
        effort=fields.get("effort", ""),
    )
    return meta, body


def load_skill(skill_dir: Path, source: str) -> Skill | None:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        return None
    meta, body = parse_skill_md(skill_path)
    return Skill(
        metadata=meta,
        content=body,
        source=source,
        source_path=str(skill_path),
    )


def load_all(skills_dir: Path, source: str) -> list[Skill]:
    results: list[Skill] = []
    for skill_dir in discover_skills(skills_dir):
        skill = load_skill(skill_dir, source)
        if skill:
            results.append(skill)
    return results
