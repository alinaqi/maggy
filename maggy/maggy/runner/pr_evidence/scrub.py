"""Secret-scan every free-text field of the evidence record before it reaches the PR body
(RFC §2.6.9, AC 5.2). Check reasons carry raw test traces, council findings and errors come
from models, so a field that looks secret is replaced by the detector labels, never shown."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from maggy.review.models import Finding
from maggy.runner.pr_evidence.models import EvidenceRecord
from maggy.runner.verify.secret_scan import scan_text


def scrub(record: EvidenceRecord, env: Mapping[str, str]) -> EvidenceRecord:
    return replace(record,
                   rows=tuple(replace(row, detail=safe(row.detail, env)) for row in record.rows),
                   gaps=tuple(safe(gap, env) for gap in record.gaps),
                   findings=tuple(_finding(f, env) for f in record.findings),
                   release_impact=safe(record.release_impact, env))


def safe(text: str, env: Mapping[str, str]) -> str:
    """`text`, or what the scan found in it when it looks secret."""
    found = scan_text(text, env)
    return f"(withheld: secret scan: {', '.join(found)})" if found else text


def _finding(finding: Finding, env: Mapping[str, str]) -> Finding:
    return finding.model_copy(update={
        "file": safe(finding.file, env), "title": safe(finding.title, env),
        "detail": safe(finding.detail, env)})
