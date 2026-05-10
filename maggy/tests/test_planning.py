"""Tests for dual-model planning orchestrator."""

from __future__ import annotations

from maggy.models.plan import Plan, PlanDiff, PlanStep
from maggy.planning import (
    DUAL_PLAN_THRESHOLD,
    PlanRequest,
    PlanningService,
    _similar,
)


class TestPlanModels:
    def test_plan_step_count(self):
        p = Plan(
            task="test", model="claude",
            steps=[
                PlanStep(description="step 1"),
                PlanStep(description="step 2"),
            ],
        )
        assert p.step_count == 2

    def test_plan_diff_agreement_ratio(self):
        d = PlanDiff(
            agreed=["a", "b"],
            conflicts=[],
            primary_only=["c"],
            counter_only=[],
        )
        assert d.agreement_ratio == 2 / 3

    def test_plan_diff_empty(self):
        d = PlanDiff()
        assert d.agreement_ratio == 1.0
        assert d.conflict_count == 0


class TestPlanningService:
    def test_below_threshold_single_plan(self, mock_cfg):
        svc = PlanningService(mock_cfg)
        req = PlanRequest(task="fix typo", blast_score=2)
        result = svc.plan_task(req)
        assert result["mode"] == "single"
        assert result["diff"] is None

    def test_above_threshold_dual_plan(self, mock_cfg):
        svc = PlanningService(mock_cfg)
        req = PlanRequest(
            task="refactor auth", blast_score=6,
        )
        result = svc.plan_task(req)
        assert result["mode"] == "dual"
        assert result["diff"] is not None

    def test_generate_plan(self, mock_cfg):
        svc = PlanningService(mock_cfg)
        plan = svc.generate_plan("add feature", "claude")
        assert plan.task == "add feature"
        assert plan.model == "claude"
        assert plan.step_count >= 1

    def test_diff_plans_identical(self, mock_cfg):
        svc = PlanningService(mock_cfg)
        p1 = svc.generate_plan("task", "claude")
        p2 = svc.generate_plan("task", "codex")
        diff = svc.diff_plans(p1, p2)
        assert len(diff.agreed) == 3

    def test_should_dual_plan_boundary(self, mock_cfg):
        svc = PlanningService(mock_cfg)
        assert not svc.should_dual_plan(3)
        assert svc.should_dual_plan(4)
        assert svc.should_dual_plan(10)


class TestSimilarity:
    def test_similar_strings(self):
        assert _similar(
            "Implement auth module",
            "Implement auth service",
        )

    def test_dissimilar_strings(self):
        assert not _similar(
            "Add login button",
            "Fix database query",
        )

    def test_empty_string(self):
        assert not _similar("", "hello")
