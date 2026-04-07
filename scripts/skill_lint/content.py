"""Content quality checks (CQ001-CQ006)."""

from __future__ import annotations

import re
from pathlib import Path

from . import Finding, Severity

# ASCII art box characters (outside code blocks)
ASCII_ART_RE = re.compile(
    r'[╔╗╚╝╠╣╦╩╬║═│┌┐└┘├┤┬┴┼─┃━┏┓┗┛┣┫┳┻╋]'
    r'|[+|]{2,}\s*[-=]{3,}'
    r'|[-=]{3,}\s*[+|]{2,}'
    r'|^\s*[+][\-+]{3,}[+]\s*$'
    r'|^\s*[|].*[|]\s*$'
)

VAGUE_PHRASES = [
    'follow best practices',
    'ensure quality',
    'as appropriate',
    'when necessary',
    'use proper',
    'handle appropriately',
    'do the right thing',
    'be careful',
    'use common sense',
    'as needed',
]

FILLER_WORDS_RE = re.compile(
    r'\b(MANDATORY|NON-NEGOTIABLE|ABSOLUTELY|CRITICAL|MUST ALWAYS|'
    r'NEVER EVER|UNDER NO CIRCUMSTANCES|WITHOUT EXCEPTION|'
    r'ZERO TOLERANCE|NO EXCEPTIONS)\b',
    re.IGNORECASE
)

STALE_LOAD_RE = re.compile(r'\*?Load with:\s+\S+\.md\*?', re.IGNORECASE)


def _in_code_block(lines: list[str], target_idx: int) -> bool:
    """Check if a line index is inside a fenced code block."""
    in_fence = False
    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_fence = not in_fence
        if i == target_idx:
            return in_fence
    return False


def check(skill_path: Path, skill_dir: Path, skills_dir: Path) -> list[Finding]:
    """Run content quality checks on a single skill."""
    findings: list[Finding] = []

    if not skill_path.exists():
        return findings

    content = skill_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Check for inline suppression in first 10 lines
    suppressed: set[str] = set()
    for line in lines[:10]:
        if '<!-- skill-lint: disable=' in line:
            start = line.index('disable=') + 8
            end = line.index('-->', start) if '-->' in line[start:] else len(line)
            rules = line[start:end].strip().rstrip(' >')
            for rule in rules.split(','):
                suppressed.add(rule.strip())

    # CQ001: no ASCII art boxes outside code blocks
    if 'CQ001' not in suppressed:
        ascii_art_lines = []
        for i, line in enumerate(lines):
            if not _in_code_block(lines, i) and ASCII_ART_RE.search(line):
                ascii_art_lines.append(i + 1)
        if ascii_art_lines:
            sample = ascii_art_lines[:3]
            findings.append(Finding(
                rule_id='CQ001',
                severity=Severity.WARNING,
                message=f'ASCII art detected outside code blocks (lines: {sample})',
                line=ascii_art_lines[0],
                suggestion='Remove decorative ASCII art to save tokens'
            ))

    # CQ002: no vague phrases
    if 'CQ002' not in suppressed:
        vague_found = []
        for i, line in enumerate(lines):
            if _in_code_block(lines, i):
                continue
            lower = line.lower()
            for phrase in VAGUE_PHRASES:
                if phrase in lower:
                    vague_found.append((i + 1, phrase))
        if vague_found:
            sample = vague_found[:3]
            phrases = ', '.join(f'"{p}" (L{n})' for n, p in sample)
            findings.append(Finding(
                rule_id='CQ002',
                severity=Severity.INFO,
                message=f'Vague phrases found: {phrases}',
                line=vague_found[0][0],
                suggestion='Replace vague guidance with specific, actionable instructions'
            ))

    # CQ003: filler intensity <= 2 per 100 lines
    if 'CQ003' not in suppressed:
        filler_count = 0
        for i, line in enumerate(lines):
            if not _in_code_block(lines, i):
                filler_count += len(FILLER_WORDS_RE.findall(line))
        if len(lines) > 0:
            intensity = (filler_count / len(lines)) * 100
            if intensity > 2:
                findings.append(Finding(
                    rule_id='CQ003',
                    severity=Severity.WARNING,
                    message=f'Filler intensity {intensity:.1f} per 100 lines (max: 2.0)',
                    suggestion='Reduce emphatic language (MANDATORY, NON-NEGOTIABLE, etc.)'
                ))

    # CQ004: >= 1 code block per 50 lines of content
    if 'CQ004' not in suppressed:
        code_blocks = content.count('```') // 2
        content_lines = len([l for l in lines if l.strip()])
        if content_lines >= 50:
            expected = content_lines / 50
            if code_blocks < expected:
                findings.append(Finding(
                    rule_id='CQ004',
                    severity=Severity.WARNING,
                    message=f'{code_blocks} code blocks for {content_lines} content lines '
                            f'(expected >= {int(expected)})',
                    suggestion='Add concrete code examples to illustrate patterns'
                ))

    # CQ005: no stale "Load with:" references
    if 'CQ005' not in suppressed:
        for i, line in enumerate(lines):
            if not _in_code_block(lines, i) and STALE_LOAD_RE.search(line):
                findings.append(Finding(
                    rule_id='CQ005',
                    severity=Severity.WARNING,
                    message=f'Stale "Load with:" reference at line {i + 1}',
                    line=i + 1,
                    suggestion='Remove stale loading instructions'
                ))
                break  # One finding is enough

    # CQ006: H1 heading present after frontmatter
    if 'CQ006' not in suppressed:
        # Find end of frontmatter
        in_fm = False
        fm_end = 0
        for i, line in enumerate(lines):
            if line.strip() == '---':
                if not in_fm:
                    in_fm = True
                else:
                    fm_end = i
                    break

        has_h1 = False
        for line in lines[fm_end:]:
            if line.strip().startswith('# '):
                has_h1 = True
                break

        if not has_h1:
            findings.append(Finding(
                rule_id='CQ006',
                severity=Severity.WARNING,
                message='No H1 heading found after frontmatter',
                suggestion='Add a top-level heading: # Skill Name'
            ))

    return findings
