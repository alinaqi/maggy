"""Tests for routing service."""

import pytest
from pathlib import Path

from maggy.routing import RoutingContext, RoutingService
from maggy.config import MaggyConfig, StorageConfig


@pytest.fixture
def service(tmp_path: Path) -> RoutingService:
    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "maggy.db")),
    )
    return RoutingService(cfg)


class TestRoutingService:
    def test_low_blast_routes_cheap(self, service):
        ctx = RoutingContext(blast_score=2, task_type="docs")
        decision = service.route(ctx)
        name = decision.primary if isinstance(decision.primary, str) else decision.primary.name
        assert name in ("kimi", "local", "deepseek")

    def test_high_blast_routes_premium(self, service):
        ctx = RoutingContext(blast_score=9, task_type="refactor")
        decision = service.route(ctx)
        name = decision.primary if isinstance(decision.primary, str) else decision.primary.name
        assert name in ("claude", "gpt")

    def test_security_adds_validator(self, service):
        ctx = RoutingContext(
            blast_score=8, security_sensitive=True,
        )
        decision = service.route(ctx)
        assert decision.validator is not None

    def test_record_and_learn(self, service):
        # Record enough to build learned preference
        for _ in range(6):
            service.record_outcome("kimi", "docs", 2, 0.95)
        ctx = RoutingContext(blast_score=2, task_type="docs")
        decision = service.route(ctx)
        assert decision.primary == "kimi"

    def test_blast_tier_mapping(self, service):
        assert service._blast_tier(0) == "low"
        assert service._blast_tier(3) == "low"
        assert service._blast_tier(5) == "medium"
        assert service._blast_tier(8) == "high"

    def test_heatmap_empty(self, service):
        assert service.get_heatmap() == []
