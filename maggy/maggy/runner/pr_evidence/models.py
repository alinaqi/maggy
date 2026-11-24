"""Shapes of the PR evidence record (factory doc §5 'Publish the evidence')."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from maggy.review.models import Finding, Severity

RowVerdict = Literal["passed", "failed", "blocked", "pending", "not applicable"]
Gate = Literal["open", "failed", "waiting"]


@dataclass(frozen=True)
class ArtifactRef:
    path: str  # relative to the runner state dir: artifacts stay local
    sha256: str
    kind: str  # log, actual, expected, diff, proposed (with the viewport when there is one)


@dataclass(frozen=True)
class CriterionRow:
    criterion_id: str
    verdict: RowVerdict
    checks: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class EvidenceRecord:
    ref: str
    spec_version: str
    sha: str
    rows: tuple[CriterionRow, ...]
    gaps: tuple[str, ...] = ()
    release_impact: str = ""
    findings: tuple[Finding, ...] = ()  # the review council's blocking findings
    uploads: tuple[tuple[str, str], ...] = ()  # (artifact path, uploaded url)
    council_failed: bool = False


def gate(record: EvidenceRecord) -> Gate:
    """failed: a required criterion failed or the review blocks (back to build); waiting: a
    required criterion is pending or blocked, or the review could not run (a human); else
    open. `not applicable` (recorded by a human) is the only verdict that is not required."""
    verdicts = {row.verdict for row in record.rows}
    if "failed" in verdicts or any(f.severity == Severity.blocking for f in record.findings):
        return "failed"
    if not record.rows or verdicts - {"passed", "not applicable"} or record.council_failed:
        return "waiting"
    return "open"
