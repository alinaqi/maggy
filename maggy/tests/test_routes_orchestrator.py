"""Tests for orchestrator API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_orchestrator import router
from maggy.config import DashboardConfig, MaggyConfig
from maggy.orchestrator.models import Task
from maggy.services.orchestrator import TeamSession


def _app() -> FastAPI:
    app = FastAPI()
    app.state.cfg = MaggyConfig(dashboard=DashboardConfig(auth_mode="local"))
    app.state.orchestrator = MagicMock()
    app.state.provider = AsyncMock()
    app.include_router(router)
    return app


class TestSpawnEndpoint:
    def test_spawn_returns_team(self):
        app = _app()
        session = TeamSession(
            team_id="tm1", task_id="t1",
            subtasks=[Task(title="sub", source="test", source_ref="t1")],
        )
        app.state.orchestrator.spawn_team = AsyncMock(return_value=session)
        app.state.orchestrator.decompose = AsyncMock(
            return_value=[Task(title="sub", source="test", source_ref="t1")],
        )
        app.state.provider.get_task = AsyncMock(return_value=MagicMock(title="parent"))
        client = TestClient(app)
        resp = client.post("/api/orchestrator/spawn", json={"task_id": "t1"})
        assert resp.status_code == 201
        assert resp.json()["team_id"] == "tm1"


class TestListEndpoint:
    def test_list_returns_teams(self):
        app = _app()
        app.state.orchestrator.list_teams.return_value = []
        client = TestClient(app)
        resp = client.get("/api/orchestrator/teams")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetEndpoint:
    def test_get_returns_team(self):
        app = _app()
        session = TeamSession(
            team_id="tm1", task_id="t1", subtasks=[],
        )
        app.state.orchestrator.get_team.return_value = session
        client = TestClient(app)
        resp = client.get("/api/orchestrator/teams/tm1")
        assert resp.status_code == 200

    def test_get_missing_returns_404(self):
        app = _app()
        app.state.orchestrator.get_team.return_value = None
        client = TestClient(app)
        resp = client.get("/api/orchestrator/teams/nope")
        assert resp.status_code == 404


class TestCancelEndpoint:
    def test_cancel_returns_ok(self):
        app = _app()
        app.state.orchestrator.cancel_team = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/orchestrator/teams/tm1/cancel")
        assert resp.status_code == 200
