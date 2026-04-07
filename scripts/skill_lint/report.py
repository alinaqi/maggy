"""Output formatters for skill-lint results."""

from __future__ import annotations

import json
from collections import defaultdict

from . import Finding, Severity


def format_text(
    results: dict[str, list[Finding]],
    min_severity: Severity = Severity.INFO
) -> str:
    """Format findings as human-readable text grouped by severity then skill."""
    severity_order = [Severity.ERROR, Severity.WARNING, Severity.INFO]
    severity_rank = {s: i for i, s in enumerate(severity_order)}
    min_rank = severity_rank[min_severity]

    # Group by severity
    by_severity: dict[Severity, dict[str, list[Finding]]] = defaultdict(
        lambda: defaultdict(list)
    )

    total_errors = 0
    total_warnings = 0
    total_info = 0

    for skill_name, findings in sorted(results.items()):
        for f in findings:
            if severity_rank[f.severity] <= min_rank:
                by_severity[f.severity][skill_name].append(f)
                if f.severity == Severity.ERROR:
                    total_errors += 1
                elif f.severity == Severity.WARNING:
                    total_warnings += 1
                else:
                    total_info += 1

    lines: list[str] = []
    total_skills = len(results)
    clean_skills = sum(1 for fs in results.values() if not fs)

    for sev in severity_order:
        if sev not in by_severity:
            continue
        if severity_rank[sev] > min_rank:
            continue

        lines.append(f'\n=== {sev.value.upper()} ===')
        for skill_name, findings in sorted(by_severity[sev].items()):
            lines.append(f'\n  {skill_name}/')
            for f in findings:
                loc = f'L{f.line}' if f.line else ''
                lines.append(f'    [{f.rule_id}] {f.message} {loc}'.rstrip())
                if f.suggestion:
                    lines.append(f'      -> {f.suggestion}')

    # Summary
    lines.append(f'\n--- Summary ---')
    lines.append(f'Skills scanned: {total_skills}')
    lines.append(f'Clean: {clean_skills}')
    lines.append(f'Errors: {total_errors}  Warnings: {total_warnings}  Info: {total_info}')

    return '\n'.join(lines)


def format_json(
    results: dict[str, list[Finding]],
    min_severity: Severity = Severity.INFO
) -> str:
    """Format findings as JSON."""
    severity_order = [Severity.ERROR, Severity.WARNING, Severity.INFO]
    severity_rank = {s: i for i, s in enumerate(severity_order)}
    min_rank = severity_rank[min_severity]

    total_errors = 0
    total_warnings = 0
    total_info = 0

    skills_out: dict[str, dict] = {}
    for skill_name, findings in sorted(results.items()):
        filtered = [
            f for f in findings
            if severity_rank[f.severity] <= min_rank
        ]
        skill_findings = []
        for f in filtered:
            entry = {
                'rule_id': f.rule_id,
                'severity': f.severity.value,
                'message': f.message,
            }
            if f.line is not None:
                entry['line'] = f.line
            if f.suggestion:
                entry['suggestion'] = f.suggestion
            skill_findings.append(entry)

            if f.severity == Severity.ERROR:
                total_errors += 1
            elif f.severity == Severity.WARNING:
                total_warnings += 1
            else:
                total_info += 1

        skills_out[skill_name] = {
            'findings': skill_findings,
            'error_count': sum(1 for f in filtered if f.severity == Severity.ERROR),
            'warning_count': sum(1 for f in filtered if f.severity == Severity.WARNING),
        }

    output = {
        'summary': {
            'total_skills': len(results),
            'clean_skills': sum(
                1 for fs in results.values() if not fs
            ),
            'errors': total_errors,
            'warnings': total_warnings,
            'info': total_info,
        },
        'skills': skills_out,
    }

    return json.dumps(output, indent=2)
