"""Tests for skills models — Pydantic models for the skills system."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from maggy.skills.models import Skill, SkillMetadata, SkillSuggestion, ValidationResult


class TestSkillMetadata:
    def test_required_fields(self):
        meta = SkillMetadata(name="python", description="Python dev")
        assert meta.name == "python"
        assert meta.description == "Python dev"

    def test_defaults(self):
        meta = SkillMetadata(name="x", description="y")
        assert meta.when_to_use == ""
        assert meta.user_invocable is False
        assert meta.paths == []
        assert meta.effort == ""

    def test_full_fields(self):
        meta = SkillMetadata(
            name="react-web",
            description="React patterns",
            when_to_use="When working on React",
            user_invocable=True,
            paths=["**/*.tsx", "**/*.jsx"],
            effort="medium",
        )
        assert meta.user_invocable is True
        assert len(meta.paths) == 2
        assert meta.effort == "medium"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            SkillMetadata(description="no name")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            SkillMetadata(name="no-desc")


class TestSkill:
    def test_construction(self):
        meta = SkillMetadata(name="base", description="Base skill")
        skill = Skill(
            metadata=meta,
            content="# Base\nContent here",
            source="global",
            source_path="/home/.claude/skills/base/SKILL.md",
        )
        assert skill.metadata.name == "base"
        assert skill.source == "global"
        assert skill.is_override is False

    def test_override_flag(self):
        meta = SkillMetadata(name="python", description="Custom python")
        skill = Skill(
            metadata=meta,
            content="# Python\nOverridden",
            source="project",
            source_path="/proj/.claude/skills/python/SKILL.md",
            is_override=True,
        )
        assert skill.is_override is True

    def test_to_dict(self):
        meta = SkillMetadata(name="test", description="Test skill")
        skill = Skill(
            metadata=meta, content="body", source="global",
            source_path="/path/SKILL.md",
        )
        d = skill.model_dump()
        assert d["metadata"]["name"] == "test"
        assert d["source"] == "global"
        assert d["is_override"] is False


class TestValidationResult:
    def test_valid_by_default(self):
        vr = ValidationResult(skill_name="base")
        assert vr.is_valid is True
        assert vr.errors == 0

    def test_invalid_with_errors(self):
        vr = ValidationResult(
            skill_name="bad",
            errors=2,
            warnings=1,
            findings=[{"rule_id": "FM001", "message": "missing"}],
            is_valid=False,
        )
        assert vr.is_valid is False
        assert vr.errors == 2

    def test_warnings_still_valid(self):
        vr = ValidationResult(skill_name="ok", warnings=3)
        assert vr.is_valid is True


class TestSkillSuggestion:
    def test_construction(self):
        s = SkillSuggestion(
            fingerprint="abc123",
            content="Pattern content",
            occurrence_count=5,
            confidence=0.8,
        )
        assert s.suggested_name == ""
        assert s.occurrence_count == 5

    def test_with_name(self):
        s = SkillSuggestion(
            fingerprint="def456",
            content="x",
            occurrence_count=3,
            confidence=0.6,
            suggested_name="error-retry",
        )
        assert s.suggested_name == "error-retry"
