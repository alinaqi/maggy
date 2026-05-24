"""Pydantic models for the skills system."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """YAML frontmatter fields from SKILL.md."""

    name: str
    description: str
    when_to_use: str = ""
    user_invocable: bool = False
    paths: list[str] = Field(default_factory=list)
    effort: str = ""


class Skill(BaseModel):
    """A resolved skill with content and provenance."""

    metadata: SkillMetadata
    content: str
    source: str
    source_path: str
    is_override: bool = False


class ValidationResult(BaseModel):
    """Lint result for a single skill."""

    skill_name: str
    errors: int = 0
    warnings: int = 0
    info_count: int = 0
    findings: list[dict] = Field(default_factory=list)
    is_valid: bool = True


class SkillSuggestion(BaseModel):
    """A Mnemos-promoted pattern suggested as a new skill."""

    fingerprint: str
    content: str
    occurrence_count: int
    confidence: float
    suggested_name: str = ""
