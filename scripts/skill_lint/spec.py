"""Spec compliance checks (SP001-SP003, SR001)."""

from __future__ import annotations

from pathlib import Path

from . import Finding, Severity


def check(skill_path: Path, skill_dir: Path, skills_dir: Path) -> list[Finding]:
    """Run spec compliance checks on a single skill."""
    findings: list[Finding] = []

    # SP001: SKILL.md exists
    if not skill_path.exists():
        findings.append(Finding(
            rule_id='SP001',
            severity=Severity.ERROR,
            message='SKILL.md not found in skill directory',
            suggestion='Create SKILL.md with frontmatter and content'
        ))
        return findings

    content = skill_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    line_count = len(lines)

    # Check for inline suppression in first 10 lines
    suppressed: set[str] = set()
    for line in lines[:10]:
        if '<!-- skill-lint: disable=' in line:
            # Extract rule IDs: <!-- skill-lint: disable=SP002,SP003 -->
            start = line.index('disable=') + 8
            end = line.index('-->', start) if '-->' in line[start:] else len(line)
            rules = line[start:end].strip().rstrip(' >')
            for rule in rules.split(','):
                suppressed.add(rule.strip())

    # SP002: under 500 lines
    if line_count > 500 and 'SP002' not in suppressed:
        findings.append(Finding(
            rule_id='SP002',
            severity=Severity.WARNING,
            message=f'SKILL.md is {line_count} lines (limit: 500)',
            suggestion='Split into focused sections; move reference material to companion files'
        ))

    # SP003: under 300 lines (ideal)
    if line_count > 300 and line_count <= 500 and 'SP003' not in suppressed:
        findings.append(Finding(
            rule_id='SP003',
            severity=Severity.INFO,
            message=f'SKILL.md is {line_count} lines (ideal: under 300)',
            suggestion='Consider trimming for better token efficiency'
        ))

    # SR001: skills-ref validate (if installed)
    try:
        from skills_ref import validate as sr_validate
        problems = sr_validate(str(skill_dir))
        if problems:
            for p in problems[:5]:
                findings.append(Finding(
                    rule_id='SR001',
                    severity=Severity.WARNING,
                    message=f'skills-ref: {p}',
                ))
    except ImportError:
        pass  # skills-ref not installed, skip

    return findings
