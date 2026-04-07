"""CLI entry point for skill-lint -- Quality gates for Claude Bootstrap skills."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import Severity, __version__
from . import content, frontmatter, references, report, spec


CHECKERS = [frontmatter, spec, content, references]


def discover_skills(skills_dir: Path, skill_filter: str | None = None) -> list[Path]:
    """Find all skill directories under skills_dir."""
    if not skills_dir.is_dir():
        return []

    dirs = sorted(
        d for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    )

    if skill_filter:
        dirs = [d for d in dirs if d.name == skill_filter]

    return dirs


def lint_skill(skill_dir: Path, skills_dir: Path) -> list:
    """Run all checkers on a single skill, return findings."""
    from . import Finding
    skill_path = skill_dir / 'SKILL.md'
    findings: list[Finding] = []

    for checker in CHECKERS:
        findings.extend(checker.check(skill_path, skill_dir, skills_dir))

    return findings


def severity_from_str(s: str) -> Severity:
    """Convert string to Severity enum."""
    mapping = {
        'error': Severity.ERROR,
        'warning': Severity.WARNING,
        'info': Severity.INFO,
    }
    result = mapping.get(s.lower())
    if result is None:
        raise ValueError(f'Unknown severity: {s}')
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='skill-lint',
        description='Quality gates for Claude Bootstrap skills'
    )
    parser.add_argument(
        '--version', action='version', version=f'skill-lint {__version__}'
    )
    parser.add_argument(
        'skills_dir',
        help='Path to skills/ directory'
    )
    parser.add_argument(
        '--format', dest='output_format', default='text',
        choices=['text', 'json'],
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--severity', default='info',
        choices=['error', 'warning', 'info'],
        help='Minimum severity to show (default: info)'
    )
    parser.add_argument(
        '--skill', default=None,
        help='Lint a single skill by directory name'
    )
    parser.add_argument(
        '--fail-on', dest='fail_on', default='error',
        choices=['error', 'warning', 'info'],
        help='Exit 1 if findings at this severity or above (default: error)'
    )

    args = parser.parse_args(argv)

    skills_dir = Path(args.skills_dir).resolve()
    if not skills_dir.is_dir():
        print(f'Error: {args.skills_dir} is not a directory', file=sys.stderr)
        return 2

    skill_dirs = discover_skills(skills_dir, args.skill)
    if not skill_dirs:
        if args.skill:
            print(f'Error: skill "{args.skill}" not found in {skills_dir}', file=sys.stderr)
            return 2
        print(f'Error: no skill directories found in {skills_dir}', file=sys.stderr)
        return 2

    # Run linting
    results: dict[str, list] = {}
    for skill_dir in skill_dirs:
        findings = lint_skill(skill_dir, skills_dir)
        results[skill_dir.name] = findings

    # Format output
    min_severity = severity_from_str(args.severity)
    if args.output_format == 'json':
        output = report.format_json(results, min_severity)
    else:
        output = report.format_text(results, min_severity)

    print(output)

    # Determine exit code
    fail_severity = severity_from_str(args.fail_on)
    severity_order = [Severity.ERROR, Severity.WARNING, Severity.INFO]
    severity_rank = {s: i for i, s in enumerate(severity_order)}
    fail_rank = severity_rank[fail_severity]

    has_failures = any(
        any(
            severity_rank[f.severity] <= fail_rank
            for f in findings
        )
        for findings in results.values()
    )

    return 1 if has_failures else 0


if __name__ == '__main__':
    sys.exit(main())
