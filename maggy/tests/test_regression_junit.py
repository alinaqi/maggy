"""Classifying one named test's run from its junit report and exit code."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.regression.junit import classify

ASSERT = ('<testcase classname="tests.test_a" name="test_add"><failure message="assert 1 == 2">'
          "&gt; assert 1 == 2\ntests/test_a.py:2: AssertionError</failure></testcase>")
FIXTURE = ('<testcase classname="tests.test_a" name="test_add"><error message="failed on '
           "setup\">E fixture 'coupon_db' not found</error></testcase>")
COLLECT = ('<testcase classname="" name="tests.test_b"><error message="collection failure">'
           "E   ModuleNotFoundError: No module named 'calc'</error></testcase>")
CRASH = ('<testcase classname="t" name="test_add"><failure message="KeyError: \'x\'">'
         "E KeyError: 'x'\ntests/test_a.py:6: KeyError</failure></testcase>")
NODE = ('<testcase name="adds"><failure type="testCodeFailure" message="Expected values">'
        "AssertionError [ERR_ASSERTION]: Expected values to be equal</failure></testcase>")
PLAYWRIGHT = ('<testcase name="coupon"><failure message="coupon.spec.ts:9 rejects" '
              'type="FAILURE">Error: expect(locator).toHaveText(expected)</failure></testcase>')
PASSED = '<testcase classname="t" name="test_add" time="0.01"/>'
SKIPPED = '<testcase classname="t" name="test_add"><skipped message="later"/></testcase>'


def _report(tmp_path: Path, cases: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="s">{cases}'
                    "</testsuite></testsuites>")
    return path


@pytest.mark.parametrize("case", [
    (ASSERT, 1, "assertion"), (NODE, 1, "assertion"), (PLAYWRIGHT, 1, "assertion"),
    (FIXTURE, 1, "error"), (COLLECT, 2, "error"), (CRASH, 1, "error"),
    (ASSERT + FIXTURE, 1, "error"), (PASSED, 0, "passed"), ("", 5, "missing"),
    (SKIPPED, 0, "missing"), (PASSED, 3, "error")])
def test_kinds(tmp_path: Path, case: tuple[str, int, str]) -> None:
    cases, code, kind = case
    assert classify(_report(tmp_path, cases), code).kind == kind


def test_trace_carries_the_failure_text(tmp_path: Path) -> None:
    run = classify(_report(tmp_path, FIXTURE), 1)
    assert "fixture 'coupon_db' not found" in run.trace and run.exit_code == 1


def test_missing_or_broken_report_is_an_error(tmp_path: Path) -> None:
    missing = classify(tmp_path / "nope.xml", 1)
    assert missing.kind == "error" and "no junit report" in missing.trace
    (tmp_path / "bad.xml").write_text("<testsuites><oops")
    assert classify(tmp_path / "bad.xml", 1).kind == "error"
    assert classify(_report(tmp_path, PASSED), None).kind == "error", "timeout / no command"
