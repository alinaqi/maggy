"""Tests for system validator API routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app() -> FastAPI:
    from maggy.api.routes_system import router
    app = FastAPI()

    class _Cfg:
        class dashboard:
            auth_mode = "local"
            api_key = ""
    app.state.cfg = _Cfg()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestHardwareRoute:
    def test_detect_hardware(self, client):
        resp = client.get("/api/system/hardware")
        assert resp.status_code == 200
        data = resp.json()
        assert "ram_gb" in data
        assert "gpu" in data

    def test_suggest_models(self, client):
        resp = client.get("/api/system/suggest-models")
        assert resp.status_code == 200
        data = resp.json()
        assert "hardware" in data
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
