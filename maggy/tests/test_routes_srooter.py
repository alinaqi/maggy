"""Tests for /api/srooter/* — one-click srooter enablement from the dashboard."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from maggy.config import MaggyConfig

ENABLED = {"installed": True, "enabled": True, "key_set": True,
           "shell_routing": True, "gateway": "https://api.srooter.ai"}
DISABLED = {"installed": True, "enabled": False, "key_set": False,
            "shell_routing": False, "gateway": "https://api.srooter.ai"}


@pytest.fixture()
def client():
    from maggy.main import create_app
    app = create_app()
    app.state.cfg = MaggyConfig()
    return TestClient(app)


class TestStatus:
    @patch("maggy.services.srooter.status", return_value=DISABLED)
    def test_returns_status(self, _s, client):
        resp = client.get("/api/srooter/status")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False


class TestEnable:
    @patch("maggy.services.srooter.enable", return_value=ENABLED)
    def test_enable_with_key(self, mock_enable, client):
        resp = client.post("/api/srooter/enable", json={"api_key": "srt_abc12345"})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
        mock_enable.assert_called_once_with("srt_abc12345", "")

    @patch("maggy.services.srooter.enable", side_effect=ValueError("invalid api key"))
    def test_invalid_key_returns_422(self, _e, client):
        resp = client.post("/api/srooter/enable", json={"api_key": "bad key;"})
        assert resp.status_code == 422

    @patch("maggy.services.srooter.enable", side_effect=FileNotFoundError())
    def test_not_installed_returns_503(self, _e, client):
        resp = client.post("/api/srooter/enable", json={"api_key": "srt_abc12345"})
        assert resp.status_code == 503


class TestDisable:
    @patch("maggy.services.srooter.disable", return_value=DISABLED)
    def test_disable(self, mock_disable, client):
        resp = client.post("/api/srooter/disable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        mock_disable.assert_called_once()
