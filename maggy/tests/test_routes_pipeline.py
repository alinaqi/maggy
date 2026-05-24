"""Tests for pipeline REST endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from maggy.api.routes_pipeline import router


def _app(log_store=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_log_store = log_store
    cfg = MagicMock()
    cfg.dashboard.auth_mode = "local"
    app.state.cfg = cfg
    return app


def _store(recent_data=None, stats_data=None):
    s = MagicMock()
    s.recent.return_value = recent_data or []
    s.stats.return_value = stats_data or {
        "total_calls": 0, "total_cost": 0.0,
        "avg_latency_ms": 0.0, "success_rate": 0.0,
        "by_model": [],
    }
    return s


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_returns_logs(self):
        rows = [{"id": 1, "model": "kimi", "success": 1}]
        store = _store(recent_data=rows)
        app = _app(store)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/pipeline/logs")
        assert r.status_code == 200
        assert r.json() == rows
        store.recent.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_filters(self):
        store = _store()
        app = _app(store)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            await c.get(
                "/api/pipeline/logs",
                params={"session_id": "s1", "model": "claude", "limit": "10"},
            )
        store.recent.assert_called_once_with(
            limit=10, session_id="s1", model="claude",
        )

    @pytest.mark.asyncio
    async def test_unconfigured_returns_empty(self):
        app = _app(log_store=None)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/pipeline/logs")
        assert r.status_code == 200
        assert r.json() == []


class TestGetStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self):
        data = {
            "total_calls": 42, "total_cost": 1.5,
            "avg_latency_ms": 800.0, "success_rate": 0.95,
            "by_model": [{"model": "kimi", "calls": 42}],
        }
        store = _store(stats_data=data)
        app = _app(store)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/pipeline/stats")
        assert r.status_code == 200
        assert r.json()["total_calls"] == 42
        store.stats.assert_called_once_with("today")

    @pytest.mark.asyncio
    async def test_period_param(self):
        store = _store()
        app = _app(store)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            await c.get("/api/pipeline/stats", params={"period": "week"})
        store.stats.assert_called_once_with("week")

    @pytest.mark.asyncio
    async def test_unconfigured_returns_empty(self):
        app = _app(log_store=None)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/pipeline/stats")
        assert r.status_code == 200
        assert r.json()["total_calls"] == 0
