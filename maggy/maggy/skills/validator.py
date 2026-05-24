"""Skill validator — wraps scripts/skill_lint/ for runtime use."""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

from maggy.skills.models import ValidationResult

logger = logging.getLogger(__name__)

_lint_available = False


def _ensure_importable() -> bool:
    global _lint_available
    if _lint_available:
        return True
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts",
        Path.home() / ".claude" / ".bootstrap-dir",
    ]
    bootstrap_file = Path.home() / ".claude" / ".bootstrap-dir"
    if bootstrap_file.exists():
        bp = Path(bootstrap_file.read_text().strip()) / "scripts"
        candidates.insert(0, bp)
    for scripts_dir in candidates:
        lint_pkg = scripts_dir / "skill_lint"
        if lint_pkg.is_dir() and (lint_pkg / "__init__.py").exists():
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            _lint_available = True
            return True
    return False


def _to_result(skill_name: str, findings: list) -> ValidationResult:
    errors = sum(1 for f in findings if f.severity.value == "error")
    warnings = sum(1 for f in findings if f.severity.value == "warning")
    info_count = sum(1 for f in findings if f.severity.value == "info")
    return ValidationResult(
        skill_name=skill_name,
        errors=errors,
        warnings=warnings,
        info_count=info_count,
        findings=[
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "message": f.message,
                "line": f.line,
                "suggestion": f.suggestion,
            }
            for f in findings
        ],
        is_valid=errors == 0,
    )


class SkillValidator:
    """Validate skills using the skill_lint system."""

    def validate_skill(
        self, skill_dir: Path, skills_dir: Path,
    ) -> ValidationResult:
        if not _ensure_importable():
            return self._unavailable(skill_dir.name)
        from skill_lint.__main__ import lint_skill
        findings = lint_skill(skill_dir, skills_dir)
        return _to_result(skill_dir.name, findings)

    def validate_all(self, skills_dir: Path) -> list[ValidationResult]:
        if not _ensure_importable():
            return []
        from skill_lint.__main__ import discover_skills, lint_skill
        results: list[ValidationResult] = []
        for skill_dir in discover_skills(skills_dir):
            findings = lint_skill(skill_dir, skills_dir)
            results.append(_to_result(skill_dir.name, findings))
        return results

    def validate_content(
        self, name: str, content: str,
    ) -> ValidationResult:
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp)
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(content)
            return self.validate_skill(skill_dir, skills_dir)

    def _unavailable(self, name: str) -> ValidationResult:
        logger.warning("skill_lint not found, skipping validation")
        return ValidationResult(
            skill_name=name,
            findings=[{
                "rule_id": "SYS001",
                "severity": "warning",
                "message": "skill_lint not available",
                "line": None,
                "suggestion": "Run install.sh to install bootstrap",
            }],
            warnings=1,
        )
