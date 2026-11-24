"""Nothing free-text reaches the PR body unscanned (RFC §2.6.9, AC 5.2): check reasons and
traces (Detail column and verification gaps), review findings, council gaps and the
release impact are secret-scanned and withheld when they look secret."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from maggy.review.models import Finding, Severity
from maggy.runner.pr_evidence.build import build_record
from maggy.runner.pr_evidence.render import render_record
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VerifyOutcome
from pr_evidence_helpers import LEAK, SHA, mixed_inputs

ENTRIES = [{"criterion_id": f"AC{n}", "evidence": "unit"} for n in (1, 2, 3)]
TRACE = f'test_x: assertion: AssertionError: headers {{"Authorization": "{LEAK}"}}'


def _body(tmp_path: Path, results: list[ViewResult], env: dict | None = None) -> str:
    outcome = VerifyOutcome(SHA, [], results, ENTRIES)
    inputs = replace(mixed_inputs(tmp_path), outcome=outcome, scanned=([], {}),
                     criteria=["[AC1] one", "[AC2] two", "[AC3] three"],
                     not_applicable=frozenset())
    return render_record(build_record(inputs), env or {})


def test_failed_blocked_and_passed_reasons_are_scanned(tmp_path: Path) -> None:
    body = _body(tmp_path, [ViewResult("AC1", "", "FAIL", TRACE, check="functional"),
                            ViewResult("AC2", "", "PENDING", TRACE, blocked=True),
                            ViewResult("AC3", "", "PASS", f"ok {LEAK}", check="functional")])
    assert LEAK not in body
    assert body.count("withheld: secret scan") >= 4  # 3 Detail cells + the AC2 gap
    assert "| AC1 | failed | functional |" in body


def test_clean_reasons_are_kept(tmp_path: Path) -> None:
    body = _body(tmp_path, [ViewResult("AC1", "", "FAIL", "test_x: assert 100 == 90",
                                       check="functional")])
    assert "test_x: assert 100 == 90" in body and "withheld" not in body


def test_runner_secret_env_values_are_withheld(tmp_path: Path) -> None:
    env = {"STRIPE_SECRET": "hunter2-plain-words"}
    body = _body(tmp_path, [ViewResult("AC1", "", "FAIL", "dump hunter2-plain-words",
                                       check="functional")], env)
    assert "hunter2" not in body


def test_findings_council_gap_and_impact_are_scanned(tmp_path: Path) -> None:
    record = build_record(mixed_inputs(tmp_path))
    leaky = Finding(file="calc.py", line=3, severity=Severity.blocking,
                    title=f"leaks {LEAK}", detail=f"token {LEAK}")
    record = replace(record, findings=(leaky,), release_impact=f"impact {LEAK}",
                     gaps=(*record.gaps, f"review council failed: RuntimeError: {LEAK}"))
    body = render_record(record, {})
    assert LEAK not in body and "calc.py:3" in body


def test_default_env_is_the_runner_environment(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUPON_API_TOKEN", "plain-words-secret-value")
    record = build_record(mixed_inputs(tmp_path))
    body = render_record(replace(record, release_impact="has plain-words-secret-value"))
    assert "plain-words-secret-value" not in body
