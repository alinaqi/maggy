"""Tests for SkillValidator — wraps scripts/skill_lint/."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.skills.validator import SkillValidator

VALID_SKILL = """\
---
name: good-skill
description: A valid skill
when-to-use: When testing
user-invocable: true
effort: low
---

# Good Skill

Content with a code block:

```python
x = 1
```
"""

INVALID_SKILL = """\
No frontmatter at all.
Just content.
"""

WARNINGS_SKILL = """\
---
name: warns
description: Skill with warnings
---

Content without H1 heading.
Follow best practices and ensure quality.
"""


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    good = d / "good-skill"
    good.mkdir(parents=True)
    (good / "SKILL.md").write_text(VALID_SKILL)

    bad = d / "bad-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text(INVALID_SKILL)

    warn = d / "warns"
    warn.mkdir()
    (warn / "SKILL.md").write_text(WARNINGS_SKILL)

    return d


class TestValidateSkill:
    def test_valid_skill(self, skills_dir: Path):
        v = SkillValidator()
        result = v.validate_skill(skills_dir / "good-skill", skills_dir)
        assert result.is_valid is True
        assert result.errors == 0
        assert result.skill_name == "good-skill"

    def test_invalid_skill(self, skills_dir: Path):
        v = SkillValidator()
        result = v.validate_skill(skills_dir / "bad-skill", skills_dir)
        assert result.is_valid is False
        assert result.errors > 0

    def test_warnings_skill(self, skills_dir: Path):
        v = SkillValidator()
        result = v.validate_skill(skills_dir / "warns", skills_dir)
        assert result.warnings > 0 or result.info_count > 0


class TestValidateAll:
    def test_validates_all(self, skills_dir: Path):
        v = SkillValidator()
        results = v.validate_all(skills_dir)
        assert len(results) == 3
        names = {r.skill_name for r in results}
        assert "good-skill" in names
        assert "bad-skill" in names

    def test_mixed_results(self, skills_dir: Path):
        v = SkillValidator()
        results = v.validate_all(skills_dir)
        valid = [r for r in results if r.is_valid]
        invalid = [r for r in results if not r.is_valid]
        assert len(valid) >= 1
        assert len(invalid) >= 1


class TestValidateContent:
    def test_valid_content(self):
        v = SkillValidator()
        result = v.validate_content("good-skill", VALID_SKILL)
        assert result.is_valid is True
        assert result.skill_name == "good-skill"

    def test_invalid_content(self):
        v = SkillValidator()
        result = v.validate_content("bad", INVALID_SKILL)
        assert result.is_valid is False

    def test_name_mismatch_detected(self):
        content = VALID_SKILL.replace("good-skill", "wrong-name")
        v = SkillValidator()
        result = v.validate_content("test-skill", content)
        has_fm004 = any(
            f.get("rule_id") == "FM004" for f in result.findings
        )
        assert has_fm004
