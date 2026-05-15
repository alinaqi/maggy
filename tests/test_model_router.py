"""Tests for dynamic model routing."""

import pytest

from maggy.process.model_router import (
    DEFAULT_TIERS,
    RoutingDecision,
    route_task,
)
from maggy.process.models import ModelTier


class TestRouteTask:
    def test_simple_task_routes_to_cheap(self):
        result = route_task(complexity_score=2)
        assert result.primary.name in ("local", "kimi")
        assert result.validator is None

    def test_medium_task_routes_to_mid(self):
        result = route_task(complexity_score=5)
        assert result.primary.cost_rank >= 2

    def test_complex_task_routes_to_claude(self):
        result = route_task(complexity_score=9)
        assert result.primary.name == "claude"

    def test_security_task_skips_cheapest(self):
        result = route_task(
            complexity_score=3,
            task_type="security",
        )
        assert result.primary.cost_rank >= 3

    def test_high_complexity_gets_validator(self):
        result = route_task(complexity_score=9)
        assert result.validator is not None
        assert result.validator.role == "validator"

    def test_security_sensitive_gets_validator(self):
        result = route_task(
            complexity_score=3,
            security_sensitive=True,
        )
        assert result.validator is not None

    def test_fallback_chain_has_higher_tiers(self):
        result = route_task(complexity_score=2)
        primary_rank = result.primary.cost_rank
        for name in result.fallback_chain:
            tier = next(
                t for t in DEFAULT_TIERS if t.name == name
            )
            assert tier.cost_rank > primary_rank

    def test_reason_contains_score(self):
        result = route_task(complexity_score=7)
        assert "complexity=7/10" in result.reason

    def test_custom_tiers(self):
        custom = [
            ModelTier(
                name="fast",
                provider="test",
                model="test-1",
                cost_rank=1,
                complexity_min=0,
                complexity_max=10,
            ),
        ]
        result = route_task(
            complexity_score=5, tiers=custom
        )
        assert result.primary.name == "fast"

    def test_zero_complexity(self):
        result = route_task(complexity_score=0)
        assert result.primary is not None

    def test_max_complexity(self):
        result = route_task(complexity_score=10)
        assert result.primary.name == "claude"
