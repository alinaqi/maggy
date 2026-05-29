"""Tests for model CRUD API routes — add, remove, validate, list."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app() -> FastAPI:
    from maggy.api.routes_models import router
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


class TestAddModelRoute:
    def test_add_cli_model(self, client, tmp_path):
        with patch(
            "maggy.api.routes_models.add_model_registry",
            return_value={
                "ok": True,
                "model": {"id": "my-llama", "tier": 5, "label": "Llama"},
            },
        ):
            resp = client.post("/api/models", json={
                "model_id": "my-llama",
                "label": "Llama",
                "access_type": "cli",
                "cli_cmd": "ollama run llama3",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]

    def test_add_api_model(self, client):
        with patch(
            "maggy.api.routes_models.add_model_registry",
            return_value={
                "ok": True,
                "model": {"id": "gpt-4", "tier": 8, "label": "GPT-4"},
            },
        ):
            resp = client.post("/api/models", json={
                "model_id": "gpt-4",
                "label": "GPT-4",
                "access_type": "api",
                "api_key": "sk-test",
                "api_base": "https://api.openai.com/v1",
            })
        assert resp.status_code == 200
        assert resp.json()["ok"]

    def test_add_model_validation_error(self, client):
        with patch(
            "maggy.api.routes_models.add_model_registry",
            return_value={"ok": False, "error": "CLI command required"},
        ):
            resp = client.post("/api/models", json={
                "model_id": "bad",
                "label": "Bad",
                "access_type": "cli",
            })
        assert resp.status_code == 200
        assert not resp.json()["ok"]


class TestRemoveModelRoute:
    def test_remove_custom_model(self, client):
        with patch(
            "maggy.api.routes_models.remove_model_registry",
            return_value={"ok": True},
        ):
            resp = client.delete("/api/models/my-llama")
        assert resp.status_code == 200
        assert resp.json()["ok"]

    def test_remove_builtin_blocked(self, client):
        with patch(
            "maggy.api.routes_models.remove_model_registry",
            return_value={
                "ok": False,
                "error": "Cannot remove built-in model 'claude-sonnet'",
            },
        ):
            resp = client.delete("/api/models/claude-sonnet")
        assert resp.status_code == 200
        assert not resp.json()["ok"]
        assert "built-in" in resp.json()["error"].lower()


class TestValidateModelRoute:
    def test_validate_cli(self, client):
        with patch(
            "maggy.api.routes_models.validate_model_registry",
            return_value={"valid": True, "path": "/usr/bin/echo"},
        ):
            resp = client.post("/api/models/check/validate", json={
                "access_type": "cli",
                "cli_cmd": "echo hello",
            })
        assert resp.status_code == 200
        assert resp.json()["valid"]

    def test_validate_api(self, client):
        with patch(
            "maggy.api.routes_models.validate_model_registry",
            return_value={"valid": True},
        ):
            resp = client.post("/api/models/check/validate", json={
                "access_type": "api",
                "api_key": "sk-test",
            })
        assert resp.status_code == 200
        assert resp.json()["valid"]

    def test_validate_failure(self, client):
        with patch(
            "maggy.api.routes_models.validate_model_registry",
            return_value={
                "valid": False,
                "error": "Binary not found: /bad/path",
            },
        ):
            resp = client.post("/api/models/check/validate", json={
                "access_type": "cli",
                "cli_cmd": "/bad/path arg",
            })
        assert resp.status_code == 200
        assert not resp.json()["valid"]


class TestListModelsRoute:
    def test_list_includes_custom_flag(self, client):
        with patch(
            "maggy.api.routes_models.list_models_registry",
            return_value=[
                {"id": "claude-sonnet", "tier": 11, "custom": False},
                {"id": "my-llama", "tier": 5, "custom": True},
            ],
        ):
            resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        custom = [m for m in data["models"] if m.get("custom")]
        assert len(custom) == 1
