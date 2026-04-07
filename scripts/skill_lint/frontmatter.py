"""Frontmatter validation checks (FM001-FM009)."""

from __future__ import annotations

import re
from pathlib import Path

from . import Finding, Severity


def parse_frontmatter(content: str) -> tuple[dict[str, str], int]:
    """Parse YAML frontmatter from between first --- pair.

    Returns (fields_dict, end_line_number).
    Only parses simple key: value pairs and YAML inline arrays [a, b].
    """
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        return {}, 0

    fields: dict[str, str] = {}
    end_line = 0
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == '---':
            end_line = i
            break
        match = re.match(r'^(\w[\w-]*)\s*:\s*(.*)', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            fields[key] = value

    return fields, end_line


NAME_PATTERN = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')


def check(skill_path: Path, skill_dir: Path, skills_dir: Path) -> list[Finding]:
    """Run all frontmatter checks on a single skill."""
    findings: list[Finding] = []
    content = skill_path.read_text(encoding='utf-8')
    dir_name = skill_dir.name

    # FM001: frontmatter delimiters present
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        findings.append(Finding(
            rule_id='FM001',
            severity=Severity.ERROR,
            message='SKILL.md missing YAML frontmatter (must start with ---)',
            line=1,
            suggestion='Add frontmatter: ---\\nname: ' + dir_name + '\\ndescription: ...\\n---'
        ))
        return findings  # Can't check other rules without frontmatter

    fields, end_line = parse_frontmatter(content)
    if end_line == 0:
        findings.append(Finding(
            rule_id='FM001',
            severity=Severity.ERROR,
            message='YAML frontmatter not closed (missing second ---)',
            line=1,
            suggestion='Add closing --- after frontmatter fields'
        ))
        return findings

    # FM002: name field present
    name = fields.get('name', '').strip()
    if not name:
        findings.append(Finding(
            rule_id='FM002',
            severity=Severity.ERROR,
            message="'name' field missing or empty in frontmatter",
            line=None,
            suggestion=f'Add: name: {dir_name}'
        ))

    # FM003: description field present
    desc = fields.get('description', '').strip()
    if not desc:
        findings.append(Finding(
            rule_id='FM003',
            severity=Severity.ERROR,
            message="'description' field missing or empty in frontmatter",
            line=None,
            suggestion='Add: description: One-line description of what this skill does'
        ))

    # FM004: name matches directory name
    if name and name != dir_name:
        findings.append(Finding(
            rule_id='FM004',
            severity=Severity.ERROR,
            message=f"name '{name}' does not match directory name '{dir_name}'",
            line=None,
            suggestion=f'Change to: name: {dir_name}'
        ))

    # FM005: name format (lowercase, hyphens, 1-64 chars)
    if name:
        if len(name) > 64:
            findings.append(Finding(
                rule_id='FM005',
                severity=Severity.ERROR,
                message=f'name is {len(name)} chars (max 64)',
                line=None
            ))
        elif not NAME_PATTERN.match(name):
            findings.append(Finding(
                rule_id='FM005',
                severity=Severity.ERROR,
                message=f"name '{name}' must be lowercase alphanumeric with hyphens",
                line=None,
                suggestion='Use only lowercase letters, numbers, and hyphens'
            ))

    # FM006: description length
    if desc:
        if len(desc) > 1024:
            findings.append(Finding(
                rule_id='FM006',
                severity=Severity.WARNING,
                message=f'description is {len(desc)} chars (max 1024)',
                line=None,
                suggestion='Shorten description to under 1024 characters'
            ))

    # FM007: when-to-use present
    if 'when-to-use' not in fields:
        findings.append(Finding(
            rule_id='FM007',
            severity=Severity.WARNING,
            message="'when-to-use' field missing",
            line=None,
            suggestion='Add: when-to-use: When to activate this skill'
        ))

    # FM008: user-invocable present
    if 'user-invocable' not in fields:
        findings.append(Finding(
            rule_id='FM008',
            severity=Severity.INFO,
            message="'user-invocable' field missing",
            line=None,
            suggestion='Add: user-invocable: true|false'
        ))

    # FM009: effort field valid
    effort = fields.get('effort', '').strip()
    if effort and effort not in ('low', 'medium', 'high'):
        findings.append(Finding(
            rule_id='FM009',
            severity=Severity.INFO,
            message=f"effort '{effort}' is not one of: low, medium, high",
            line=None
        ))
    elif not effort:
        findings.append(Finding(
            rule_id='FM009',
            severity=Severity.INFO,
            message="'effort' field missing",
            line=None,
            suggestion='Add: effort: low|medium|high'
        ))

    return findings
