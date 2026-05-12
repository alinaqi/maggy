"""Tests for RoutingService — routing decisions and learning."""

from __future__ import annotations

from maggy.routing import RoutingContext, RoutingService
from maggy.scores import MIN_SAMPLES


class TestRoutingDecisions:
    def test_low_complexity_routes_cheap(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        ctx = RoutingContext(blast_score=1, task_type="general")
        decision = rs.route(ctx)
        name = (
            decision.primary
            if isinstance(decision.primary, str)
            else decision.primary.name
        )
        assert name in ("kimi", "local", "deepseek")

    def test_high_complexity_routes_premium(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        ctx = RoutingContext(blast_score=9, task_type="general")
        decision = rs.route(ctx)
        name = (
            decision.primary
            if isinstance(decision.primary, str)
            else decision.primary.name
        )
        assert name in ("codex", "claude")

    def test_security_sensitive_avoids_cheap(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        ctx = RoutingContext(
            blast_score=3,
            task_type="security",
            security_sensitive=True,
        )
        decision = rs.route(ctx)
        name = (
            decision.primary
            if isinstance(decision.primary, str)
            else decision.primary.name
        )
        assert name in ("codex", "claude")


class TestRoutingLearning:
    def test_record_outcome(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        rs.record_outcome("claude", "bug", 8, 0.95)
        hm = rs.get_heatmap()
        assert len(hm) == 1

    def test_learned_override(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        # Seed enough data for learning
        for _ in range(MIN_SAMPLES + 1):
            rs.record_outcome("codex", "bug", 2, 0.99)
        ctx = RoutingContext(blast_score=2, task_type="bug")
        decision = rs.route(ctx)
        name = (
            decision.primary
            if isinstance(decision.primary, str)
            else decision.primary.name
        )
        assert name == "codex"

    def test_blast_tier_mapping(self, mock_cfg):
        rs = RoutingService(mock_cfg)
        assert rs._blast_tier(0) == "low"
        assert rs._blast_tier(3) == "low"
        assert rs._blast_tier(5) == "medium"
        assert rs._blast_tier(8) == "high"
