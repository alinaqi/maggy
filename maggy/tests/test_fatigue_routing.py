"""Tests for fatigue-aware model routing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from maggy.mnemos.constants import (
    FATIGUE_PARALLEL_BLOCK,
    FATIGUE_ROUTING_ESCALATE,
    FATIGUE_ROUTING_PREMIUM,
)
from maggy.process.model_router import route_task
from maggy.routing import RoutingContext


class TestFatigueRoutingConstants:
    def test_threshold_ordering(self):
        assert FATIGUE_PARALLEL_BLOCK < FATIGUE_ROUTING_ESCALATE
        assert FATIGUE_ROUTING_ESCALATE < FATIGUE_ROUTING_PREMIUM

    def test_escalate_value(self):
        assert FATIGUE_ROUTING_ESCALATE == 0.60

    def test_premium_value(self):
        assert FATIGUE_ROUTING_PREMIUM == 0.75

    def test_parallel_block_value(self):
        assert FATIGUE_PARALLEL_BLOCK == 0.50


class TestRoutingContextFatigue:
    def test_default_fatigue_is_zero(self):
        ctx = RoutingContext()
        assert ctx.fatigue_score == 0.0

    def test_custom_fatigue(self):
        ctx = RoutingContext(fatigue_score=0.7)
        assert ctx.fatigue_score == 0.7


class TestSelectPrimaryFatigue:
    def test_escalate_skips_cheap_at_pre_sleep(self):
        r = route_task(complexity_score=2, fatigue=0.65)
        assert r.primary.cost_rank >= 3

    def test_premium_forced_at_rem(self):
        r = route_task(complexity_score=2, fatigue=0.80)
        assert r.primary.cost_rank >= 4

    def test_no_escalation_below_threshold(self):
        r = route_task(complexity_score=2, fatigue=0.30)
        assert r.primary.cost_rank <= 2

    def test_fatigue_at_escalate_boundary(self):
        r = route_task(complexity_score=2, fatigue=0.60)
        assert r.primary.cost_rank >= 3

    def test_fatigue_at_premium_boundary(self):
        r = route_task(complexity_score=2, fatigue=0.75)
        assert r.primary.cost_rank >= 4

    def test_high_blast_unaffected_by_fatigue(self):
        """High complexity already routes to premium — fatigue is no-op."""
        low = route_task(complexity_score=9, fatigue=0.0)
        high = route_task(complexity_score=9, fatigue=0.80)
        assert low.primary.cost_rank >= 3
        assert high.primary.cost_rank >= 3


class TestDecideEndpointFatigue:
    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from maggy.api.routes_routing import router

        app = FastAPI()
        app.include_router(router)
        svc = MagicMock()
        svc.route.return_value = MagicMock(
            primary="claude", validator=None,
            fallback_chain=[], reason="test",
        )
        app.state.routing = svc
        cfg = MagicMock()
        cfg.dashboard.auth_mode = "local"
        app.state.cfg = cfg
        return TestClient(app)

    def test_default_fatigue_zero(self, client):
        client.get(
            "/api/routing/decide?blast=2",
            headers={"x-api-key": "test"},
        )
        ctx = client.app.state.routing.route.call_args[0][0]
        assert ctx.fatigue_score == 0.0

    def test_fatigue_passed_through(self, client):
        client.get(
            "/api/routing/decide?blast=2&fatigue=0.7",
            headers={"x-api-key": "test"},
        )
        ctx = client.app.state.routing.route.call_args[0][0]
        assert ctx.fatigue_score == pytest.approx(0.7)
