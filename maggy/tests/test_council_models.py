"""Tests for council dataclasses."""

import pytest


class TestContextPackage:
    def test_create_minimal(self):
        from maggy.council.models import ContextPackage
        ctx = ContextPackage(goal="fix bug", plan_text="patch file")
        assert ctx.goal == "fix bug"
        assert ctx.code_diff == ""
        assert ctx.affected_code == []

    def test_summary_truncates(self):
        from maggy.council.models import ContextPackage
        ctx = ContextPackage(goal="x" * 200, plan_text="y" * 200)
        s = ctx.summary()
        assert len(s) <= 300


class TestReviewerVote:
    def test_approve(self):
        from maggy.council.models import ReviewerVote
        v = ReviewerVote(reviewer_id="ds", round_num=1, verdict="APPROVE")
        assert v.is_approve

    def test_reject(self):
        from maggy.council.models import ReviewerVote
        v = ReviewerVote(reviewer_id="ds", round_num=1, verdict="REJECT")
        assert not v.is_approve

    def test_to_dict(self):
        from maggy.council.models import ReviewerVote
        v = ReviewerVote(
            reviewer_id="kimi", round_num=2,
            verdict="APPROVE", reasoning="looks good"
        )
        d = v.to_dict()
        assert d["reviewer_id"] == "kimi"
        assert d["round"] == 2
        assert d["verdict"] == "APPROVE"


class TestDeliberationResult:
    def test_approved_when_threshold_met(self):
        from maggy.council.models import ReviewerVote, DeliberationResult
        votes = [
            ReviewerVote("a", 1, "APPROVE"),
            ReviewerVote("b", 1, "APPROVE"),
            ReviewerVote("c", 1, "REJECT"),
        ]
        r = DeliberationResult(
            final_votes=votes, rounds_needed=1, threshold=2
        )
        assert r.approved
        assert r.approve_count == 2

    def test_rejected_below_threshold(self):
        from maggy.council.models import ReviewerVote, DeliberationResult
        votes = [
            ReviewerVote("a", 1, "REJECT"),
            ReviewerVote("b", 1, "REJECT"),
            ReviewerVote("c", 1, "APPROVE"),
        ]
        r = DeliberationResult(
            final_votes=votes, rounds_needed=1, threshold=2
        )
        assert not r.approved

    def test_consensus_all_agree(self):
        from maggy.council.models import ReviewerVote, DeliberationResult
        votes = [
            ReviewerVote("a", 1, "APPROVE"),
            ReviewerVote("b", 1, "APPROVE"),
        ]
        r = DeliberationResult(
            final_votes=votes, rounds_needed=1, threshold=2
        )
        assert r.consensus


class TestBlastAnalysis:
    def test_score_low(self):
        from maggy.council.models import BlastAnalysis
        b = BlastAnalysis(files_changed=2, functions_affected=3,
                          subsystems_crossed=1, test_coverage=0.9)
        assert b.severity == "low"

    def test_score_medium(self):
        from maggy.council.models import BlastAnalysis
        b = BlastAnalysis(files_changed=6, functions_affected=15,
                          subsystems_crossed=2, test_coverage=0.5)
        assert b.severity == "medium"

    def test_score_high(self):
        from maggy.council.models import BlastAnalysis
        b = BlastAnalysis(files_changed=12, functions_affected=40,
                          subsystems_crossed=3, test_coverage=0.3)
        assert b.severity == "high"

    def test_critical_auth(self):
        from maggy.council.models import BlastAnalysis
        b = BlastAnalysis(files_changed=1, functions_affected=1,
                          subsystems_crossed=1, test_coverage=1.0,
                          has_auth_changes=True)
        assert b.severity == "critical"

    def test_critical_public_api(self):
        from maggy.council.models import BlastAnalysis
        b = BlastAnalysis(files_changed=1, functions_affected=1,
                          subsystems_crossed=1, test_coverage=1.0,
                          has_public_api_changes=True)
        assert b.severity == "critical"


class TestValidationClassification:
    def test_objective(self):
        from maggy.council.models import ValidationClassification
        v = ValidationClassification(
            objective_checks=["tests", "types", "lint"],
            subjective_reasons=[]
        )
        assert v.validation_type == "OBJECTIVE"
        assert v.auto_executable

    def test_subjective(self):
        from maggy.council.models import ValidationClassification
        v = ValidationClassification(
            objective_checks=[],
            subjective_reasons=["UI change"]
        )
        assert v.validation_type == "SUBJECTIVE"
        assert not v.auto_executable

    def test_hybrid(self):
        from maggy.council.models import ValidationClassification
        v = ValidationClassification(
            objective_checks=["tests"],
            subjective_reasons=["copy change"]
        )
        assert v.validation_type == "HYBRID"
        assert not v.auto_executable


class TestExecutionDecision:
    def test_fields(self):
        from maggy.council.models import ExecutionDecision
        d = ExecutionDecision(
            action="AUTO_EXECUTE", reason="low blast"
        )
        assert d.action == "AUTO_EXECUTE"
        assert d.rollback_point is None
        assert d.validation_steps == []
