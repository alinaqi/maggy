"""Tests for setup and onboarding routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_setup import router as setup_router
from maggy.config import (
    DashboardConfig,
    MaggyConfig,
    StorageConfig,
)


@pytest.fixture
def setup_app(tmp_path: Path) -> FastAPI:
    """App with setup router only."""
    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "s.db")),
        dashboard=DashboardConfig(auth_mode="local"),
    )
    app = FastAPI()
    app.state.cfg = cfg
    app.state.configured = True
    app.state.mode = "local"
    app.include_router(setup_router)
    return app


@pytest.fixture
def client(setup_app: FastAPI) -> TestClient:
    return TestClient(setup_app)


class TestSetupStatus:
    def test_returns_steps(self, client: TestClient):
        resp = client.get("/api/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert len(data["steps"]) == 5
        assert data["mode"] == "local"

    def test_missing_token_detected(
        self, client: TestClient,
    ):
        resp = client.get("/api/setup/status")
        data = resp.json()
        token_step = data["steps"][0]
        assert token_step["label"] == "GitHub token"
        assert token_step["status"] == "missing"

    def test_progress_format(self, client: TestClient):
        resp = client.get("/api/setup/status")
        data = resp.json()
        assert "/" in data["progress"]

    def test_configured_false_in_local(
        self, client: TestClient,
    ):
        resp = client.get("/api/setup/status")
        assert resp.json()["configured"] is False


class TestSetupConfigure:
    @patch("maggy.config.save")
    def test_updates_github_repos(
        self, mock_save, client,
    ):
        resp = client.post(
            "/api/setup/configure",
            json={
                "github_org": "protaige",
                "github_repos": ["api", "web"],
            },
        )
        assert resp.json()["saved"] is True

    @patch("maggy.config.save")
    def test_empty_body_is_noop(
        self, mock_save, client,
    ):
        resp = client.post(
            "/api/setup/configure", json={},
        )
        assert resp.json()["saved"] is True


class TestDiscoverRepos:
    def test_returns_repos(self, client: TestClient):
        resp = client.get("/api/setup/discover-repos")
        assert resp.status_code == 200
        data = resp.json()
        assert "repos" in data
        assert isinstance(data["repos"], list)
