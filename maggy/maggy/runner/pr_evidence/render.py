"""Render the evidence record as the PR body's evidence section (factory doc §5): ticket,
spec version, tested commit, gate, per-criterion table, review findings, gaps, release impact
and (only when opted in and scanned) uploaded screenshots."""

from __future__ import annotations

from maggy.review.models import Finding
from maggy.runner.pr_evidence.models import ArtifactRef, CriterionRow, EvidenceRecord, gate

GATE_TEXT = {
    "open": "open (every required criterion passed; no blocking review findings)",
    "failed": "closed (a required criterion failed or the review has blocking findings)",
    "waiting": "closed (verification is pending or blocked; waiting for a human)",
}
HEAD = ["| Criterion | Verdict | Check(s) | Evidence | Detail | Artifacts |",
        "|---|---|---|---|---|---|"]


def render_record(record: EvidenceRecord) -> str:
    lines = ["## Evidence", "", f"- Ticket: `{record.ref}`",
             f"- Spec version: `{record.spec_version}`", f"- Tested commit: `{record.sha}`",
             f"- Gate: {GATE_TEXT[gate(record)]}", "", *HEAD, *map(_row, record.rows), "",
             "### Review council", "",
             *([_finding(f) for f in record.findings] or ["No blocking findings."]), "",
             "### Verification gaps", "", *(f"- {_text(g)}" for g in record.gaps or ["none"]),
             "", "### Release impact", "", _text(record.release_impact or "not recorded"), ""]
    return "\n".join(lines + _screenshots(record))


def _row(row: CriterionRow) -> str:
    cells = [row.criterion_id, row.verdict, ", ".join(row.checks) or "-",
             ", ".join(row.evidence) or "-", _text(row.detail)[:300] or "-",
             "<br>".join(map(_artifact, row.artifacts)) or "-"]
    return "| " + " | ".join(_cell(c) if i < 5 else c for i, c in enumerate(cells)) + " |"


def _artifact(ref: ArtifactRef) -> str:
    return f"{_cell(ref.kind)} `{_cell(ref.path)}` (sha256:{ref.sha256[:12]})"


def _finding(finding: Finding) -> str:
    where = f"{finding.file}:{finding.line}" if finding.line else finding.file
    return f"- {finding.severity.value} `{_cell(where)}` {_text(finding.title)}: {_text(finding.detail)[:300]}"


def _screenshots(record: EvidenceRecord) -> list[str]:
    if not record.uploads:
        return []
    return ["### Screenshots", "", *(f"![{_cell(path)}]({url})" for path, url in record.uploads),
            ""]


def _text(text: str) -> str:
    return " ".join(str(text).split())


def _cell(text: str) -> str:
    return _text(text).replace("|", "\\|")
