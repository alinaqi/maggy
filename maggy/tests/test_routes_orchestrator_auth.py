"""Orchestrator routes require the core API key (X-API-Key) in token mode."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_orchestrator import router
from maggy.config import DashboardConfig, MaggyConfig

KEY = "secret-key"
ROUTES = [
    ("post", "/api/orchestrator/spawn", {"task_id": "t1"}),
    ("post", "/api/orchestrator/teams/tm1/cancel", None),
    ("get", "/api/orchestrator/teams", None),
    ("get", "/api/orchestrator/teams/tm1", None),
]


@pytest.fixture
def app():
    app = FastAPI()
    app.state.cfg = MaggyConfig(dashboard=DashboardConfig(auth_mode="token", api_key=KEY))
    app.state.orchestrator = MagicMock(spawn_team=AsyncMock(), decompose=AsyncMock(),
                                       cancel_team=AsyncMock())
    app.state.provider = AsyncMock()
    app.include_router(router)
    return app


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_missing_key_is_rejected(app, method, path, body):
    resp = getattr(TestClient(app), method)(path, **({"json": body} if body else {}))
    assert resp.status_code == 401
    app.state.orchestrator.spawn_team.assert_not_called()
    app.state.orchestrator.cancel_team.assert_not_called()


def test_wrong_key_is_rejected(app):
    resp = TestClient(app).post("/api/orchestrator/spawn", json={"task_id": "t1"},
                                headers={"X-API-Key": "nope"})
    assert resp.status_code == 401


def test_valid_key_reaches_handler(app):
    resp = TestClient(app).post("/api/orchestrator/teams/tm1/cancel",
                                headers={"X-API-Key": KEY})
    assert resp.status_code == 200
