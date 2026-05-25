"""Tests for executor gate decision matrix."""

import pytest

from maggy.council.models import (
    BlastAnalysis, DeliberationResult, ExecutionDecision,
    ReviewerVote, ValidationClassification
)


def _approved_result(threshold: int = 2) -> DeliberationResult:
    votes = [
        ReviewerVote("a", 1, "APPROVE"),
        ReviewerVote("b", 1, "APPROVE"),
        ReviewerVote("c", 1, "REJECT"),
    ]
    return DeliberationResult(
        final_votes=votes, rounds_needed=1, threshold=threshold
    )


def _rejected_result() -> DeliberationResult:
    votes = [
        ReviewerVote("a", 1, "REJECT"),
        ReviewerVote("b", 1, "REJECT"),
        ReviewerVote("c", 1, "REJECT"),
    ]
    return DeliberationResult(
        final_votes=votes, rounds_needed=3, threshold=2
    )


class TestExecutorGate:
    def test_council_rejected(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(1, 2, 1, 0.9)
        val = ValidationClassification(["tests"], [])
        d = decide(_rejected_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"

    def test_low_objective_auto_execute(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(2, 3, 1, 0.9)
        val = ValidationClassification(["tests", "types"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "AUTO_EXECUTE"

    def test_low_subjective_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(2, 3, 1, 0.9)
        val = ValidationClassification([], ["UI change"])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"

    def test_medium_objective_with_rollback(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(6, 15, 2, 0.85)
        val = ValidationClassification(["tests", "lint"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "AUTO_WITH_ROLLBACK"
        assert d.rollback_point is not None

    def test_medium_subjective_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(6, 15, 2, 0.6)
        val = ValidationClassification(["tests"], ["design review"])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"

    def test_high_objective_auto_with_notify(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(12, 40, 3, 0.8)
        val = ValidationClassification(["tests", "types"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "AUTO_WITH_NOTIFY"

    def test_high_subjective_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(12, 40, 3, 0.5)
        val = ValidationClassification(["tests"], ["UX flow"])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"

    def test_critical_always_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(1, 2, 1, 1.0, has_auth_changes=True)
        val = ValidationClassification(["tests", "types", "lint"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"
        assert "critical" in d.reason.lower()

    def test_critical_public_api_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(1, 2, 1, 1.0, has_public_api_changes=True)
        val = ValidationClassification(["tests"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"

    def test_medium_low_coverage_human(self):
        from maggy.council.executor_gate import decide
        blast = BlastAnalysis(6, 15, 2, 0.3)
        val = ValidationClassification(["types"], [])
        d = decide(_approved_result(), blast, val)
        assert d.action == "HUMAN_REVIEW"
