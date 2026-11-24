"""Prove one planned regression test: it must FAIL on base for an assertion, PASS on the
candidate (RFC §2.5 Verify, AC-aware RED/GREEN).

Outcomes: `proven`; `not_red` (passes on base: the test does not prove the change);
`setup_error` (collection/import/fixture error, crash or test not found on base: the test
infrastructure is broken, a distinct failure kind); `not_green` (fails on the candidate).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from maggy.runner.regression.junit import RunKind, TestRun
from maggy.runner.regression.run import ProofPlan, run_named
from maggy.worker.launch import refuse_host_checks

__all__ = ["Proof", "ProofPlan", "prove"]

Outcome = Literal["proven", "not_red", "setup_error", "not_green"]
RED_FAILURES: dict[str, Outcome] = {"passed": "not_red", "error": "setup_error",
                                    "missing": "setup_error"}


@dataclass(frozen=True)
class Proof:
    criterion_id: str
    test: str
    outcome: Outcome
    red: RunKind
    green: RunKind | None = None
    trace: str = ""


def prove(plan: ProofPlan, entry: dict) -> Proof:
    """RED then (only if RED failed by an assertion) GREEN, each in a fresh worktree."""
    criterion, test = str(entry["criterion_id"]), str(entry["regression_test_name"])
    refuse_host_checks(plan.profile, f"regression test {test}")
    red = run_named(plan, test, red=True)
    if red.kind in RED_FAILURES:
        outcome = RED_FAILURES[red.kind]
        return Proof(criterion, test, outcome, red.kind, None, _red_trace(outcome, red))
    green = run_named(plan, test, red=False)
    if green.kind == "passed":
        return Proof(criterion, test, "proven", red.kind, green.kind)
    trace = f"fails on the candidate ({green.kind}):\n{green.trace}"
    return Proof(criterion, test, "not_green", red.kind, green.kind, trace)


def _red_trace(outcome: Outcome, red: TestRun) -> str:
    if outcome == "not_red":
        return "passes on base with only the candidate's tests: it does not prove the change"
    return f"not an assertion failure on base ({red.kind}):\n{red.trace}"
