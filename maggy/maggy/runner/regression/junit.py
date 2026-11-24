"""Classify one named test's run from its junit report and exit code.

Kinds: `passed` (exit 0, at least one test ran, none failed), `assertion` (every failure is
an assertion: AssertionError, node's ERR_ASSERTION, a Playwright `expect(`), `error` (a
collection/import/fixture/setup <error>, any other exception, a crash, a timeout or no
report) and `missing` (no test ran: unknown name or only skips). The report is written by
candidate code, so it is size-capped and parsed by expat (entity-expansion protected).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RunKind = Literal["passed", "assertion", "error", "missing"]
ASSERTION_MARKERS = ("AssertionError", "ERR_ASSERTION", "expect(")
MAX_REPORT = 5_000_000
MAX_TRACE = 1500


@dataclass(frozen=True)
class TestRun:
    __test__ = False  # not a pytest class

    kind: RunKind
    exit_code: int | None
    trace: str = ""


def classify(report: Path, exit_code: int | None) -> TestRun:
    cases = _cases(report)
    if cases is None:
        return TestRun("error", exit_code, f"no junit report (exit {exit_code})")
    errors = [node for case in cases for node in case if node.tag in ("error", "failure")]
    if errors:
        kind = "assertion" if all(map(_is_assertion, errors)) else "error"
        return TestRun(kind, exit_code, _trace(errors))
    return _clean(cases, exit_code)


def _clean(cases: list[ET.Element], exit_code: int | None) -> TestRun:
    """No failure recorded: passed only when a test really ran and the exit code agrees."""
    ran = [case for case in cases if case.find("skipped") is None]
    if exit_code is not None and exit_code != 0 and ran:
        return TestRun("error", exit_code, f"exit {exit_code} with no recorded failure")
    if not ran:
        return TestRun("missing", exit_code, "the named test did not run (not found or skipped)")
    return TestRun("passed" if exit_code == 0 else "error", exit_code)


def _cases(report: Path) -> list[ET.Element] | None:
    try:
        if report.stat().st_size > MAX_REPORT:
            return None
        return list(ET.parse(report).getroot().iter("testcase"))
    except (OSError, ET.ParseError):
        return None


def _is_assertion(node: ET.Element) -> bool:
    if node.tag != "failure":
        return False
    text = (node.text or "").strip().splitlines()
    seen = " ".join([node.get("type", ""), node.get("message", ""), *text[-1:], *text[:1]])
    return any(marker in seen for marker in ASSERTION_MARKERS)


def _trace(nodes: list[ET.Element]) -> str:
    parts = [f"{node.tag}: {node.get('message', '')}\n{node.text or ''}".strip()
             for node in nodes]
    return "\n".join(parts)[:MAX_TRACE]
