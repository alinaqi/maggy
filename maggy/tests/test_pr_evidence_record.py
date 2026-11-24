"""The PR evidence record (RFC §2.5 PR row; factory doc §5 'Publish the evidence'):
per-criterion verdicts kept distinct, tested SHA, spec version, gaps and the gate."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from maggy.review.models import Finding, Severity
from maggy.runner.pr_evidence.build import build_record
from maggy.runner.pr_evidence.models import gate
from maggy.runner.pr_evidence.render import render_record
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VerifyOutcome
from pr_evidence_helpers import BLOCKING, LEAK, SHA, mixed_inputs

GOLDEN = Path(__file__).parent / "golden" / "pr_evidence" / "mixed.md"
IMPACT = "UI-only fix; pricing rules and API contract preserved."


def _mixed(tmp_path: Path):
    record = build_record(mixed_inputs(tmp_path))
    return replace(record, findings=(BLOCKING,), release_impact=IMPACT)


def test_mixed_verdict_body_matches_the_golden(tmp_path: Path) -> None:
    body = render_record(_mixed(tmp_path))
    assert body == GOLDEN.read_text()


def test_all_five_verdict_kinds_are_kept_distinct(tmp_path: Path) -> None:
    rows = {row.criterion_id: row.verdict for row in _mixed(tmp_path).rows}
    assert rows == {"AC1": "passed", "AC2": "failed", "AC3": "blocked", "AC4": "pending",
                    "AC5": "not applicable"}
    body = render_record(_mixed(tmp_path))
    assert SHA in body and "Spec version: `7`" in body


def test_withheld_artifact_is_excluded_and_recorded_as_a_gap(tmp_path: Path) -> None:
    record = build_record(mixed_inputs(tmp_path))
    [ac2] = [row for row in record.rows if row.criterion_id == "AC2"]
    assert ac2.artifacts == ()
    assert any("[AC2]" in gap and "secret scan" in gap for gap in record.gaps)
    assert LEAK not in render_record(record)


def _only(tmp_path: Path, results: list[ViewResult], entries: list[dict]):
    inputs = mixed_inputs(tmp_path)
    outcome = VerifyOutcome(SHA, [], results, entries)
    return build_record(replace(inputs, outcome=outcome, criteria=["[AC1] one", "[AC2] two"],
                                scanned=([], {}), not_applicable=frozenset()))


PASSED = [ViewResult("AC1", "", "PASS", "ok", check="functional"),
          ViewResult("AC2", "", "PASS", "ok", check="functional")]
ENTRIES = [{"criterion_id": "AC1", "evidence": "unit"}, {"criterion_id": "AC2", "evidence": "unit"}]


def test_gate_opens_only_when_every_required_criterion_passed(tmp_path: Path) -> None:
    record = _only(tmp_path, PASSED, ENTRIES)
    assert gate(record) == "open"
    nit = Finding(file="a.py", severity=Severity.nit, title="naming", detail="meh")
    assert gate(replace(record, findings=(nit,))) == "open"
    assert gate(replace(record, findings=(BLOCKING,))) == "failed"
    assert gate(replace(record, council_failed=True)) == "waiting"
    assert gate(replace(record, failed_commands=("test",))) == "failed"


def test_pending_or_unchecked_criteria_keep_the_gate_closed(tmp_path: Path) -> None:
    pending = [PASSED[0], ViewResult("AC2", "x", "PENDING", "no baseline")]
    assert gate(_only(tmp_path, pending, ENTRIES)) == "waiting"
    unchecked = _only(tmp_path, PASSED[:1], ENTRIES[:1])
    assert [r.verdict for r in unchecked.rows] == ["passed", "blocked"]
    assert gate(unchecked) == "waiting"
    manual = _only(tmp_path, PASSED[:1], [ENTRIES[0], {"criterion_id": "AC2",
                                                      "evidence": "manual"}])
    assert manual.rows[1].verdict == "pending" and gate(manual) == "waiting"
    failed = [PASSED[0], ViewResult("AC2", "", "FAIL", "boom", check="functional")]
    assert gate(_only(tmp_path, failed, ENTRIES)) == "failed"
