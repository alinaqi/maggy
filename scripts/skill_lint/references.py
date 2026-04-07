"""Cross-reference checks (RI001-RI002)."""

from __future__ import annotations

import re
from pathlib import Path

from . import Finding, Severity

# Match skill references like: skills/base, skills/security, .claude/skills/llm-patterns
SKILL_REF_RE = re.compile(
    r'(?:\.claude/)?skills/([a-z][a-z0-9-]+)'
)


def check(skill_path: Path, skill_dir: Path, skills_dir: Path) -> list[Finding]:
    """Run cross-reference checks on a single skill."""
    findings: list[Finding] = []

    if not skill_path.exists():
        return findings

    content = skill_path.read_text(encoding='utf-8')
    dir_name = skill_dir.name

    # RI001: cross-skill name references resolve to existing dirs
    existing_skills = {
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    }

    referenced = set()
    for match in SKILL_REF_RE.finditer(content):
        ref_name = match.group(1)
        if ref_name != dir_name:
            referenced.add(ref_name)

    broken = referenced - existing_skills
    if broken:
        findings.append(Finding(
            rule_id='RI001',
            severity=Severity.WARNING,
            message=f'Broken skill references: {", ".join(sorted(broken))}',
            suggestion='Fix or remove references to non-existent skills'
        ))

    # RI002: skill listed in README skills table
    readme_path = skills_dir.parent / 'README.md'
    if readme_path.exists():
        readme = readme_path.read_text(encoding='utf-8')
        # Check if skill name appears in README (in a table or list)
        if dir_name not in readme:
            findings.append(Finding(
                rule_id='RI002',
                severity=Severity.INFO,
                message=f'Skill "{dir_name}" not found in README.md',
                suggestion='Add skill to the skills table in README.md'
            ))

    return findings
