"""Tests for GET/PATCH /api/config — settings UI configurability."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from maggy.config import MaggyConfig


@pytest.fixture()
def client():
    from maggy.main import create_app
    app = create_app()
    app.state.cfg = MaggyConfig()
    return TestClient(app)


class TestGetConfig:
    def test_returns_ai_section(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "ai" in data
        assert data["ai"]["provider"] == "anthropic"

    def test_returns_budget_section(self, client):
        resp = client.get("/api/config")
        data = resp.json()
        assert "budget" in data
        assert data["budget"]["daily_limit_usd"] == 10.0

    def test_returns_dashboard_section(self, client):
        resp = client.get("/api/config")
        data = resp.json()
        assert "dashboard" in data
        assert data["dashboard"]["port"] == 8080

    def test_redacts_api_key(self, client):
        resp = client.get("/api/config")
        data = resp.json()
        assert "api_key" not in data["ai"]


class TestPatchConfig:
    @patch("maggy.config.save")
    def test_update_ai_provider(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"ai": {"provider": "openai", "model": "gpt-4o"}},
        )
        assert resp.status_code == 200
        assert resp.json()["ai"]["provider"] == "openai"
        mock_save.assert_called_once()

    @patch("maggy.config.save")
    def test_update_budget(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"budget": {"daily_limit_usd": 25.0}},
        )
        assert resp.status_code == 200
        assert resp.json()["budget"]["daily_limit_usd"] == 25.0

    @patch("maggy.config.save")
    def test_update_issue_tracker(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"issue_tracker": {"provider": "linear"}},
        )
        assert resp.status_code == 200
        assert resp.json()["issue_tracker"]["provider"] == "linear"

    @patch("maggy.config.save")
    def test_org_not_in_response(self, mock_save, client):
        resp = client.get("/api/config")
        assert "org" not in resp.json()

    @patch("maggy.config.save")
    def test_partial_update_preserves_other(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"ai": {"model": "gpt-4o"}},
        )
        assert resp.status_code == 200
        assert resp.json()["ai"]["provider"] == "anthropic"

    @patch("maggy.config.save")
    def test_rejects_secret_fields(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"ai": {"api_key": "sk-evil"}},
        )
        assert resp.status_code == 200
        assert client.app.state.cfg.ai.api_key != "sk-evil"

    @patch("maggy.config.save")
    def test_update_dashboard_port(self, mock_save, client):
        resp = client.patch(
            "/api/config",
            json={"dashboard": {"port": 9090}},
        )
        assert resp.status_code == 200
        assert resp.json()["dashboard"]["port"] == 9090
