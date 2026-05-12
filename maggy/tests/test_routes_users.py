"""Tests for the user registration endpoint."""

from __future__ import annotations

import bcrypt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_users import router
from maggy.services.users import UserService


def _app(mock_cfg) -> FastAPI:
    """Build a minimal FastAPI app with the users router."""
    app = FastAPI()
    app.state.cfg = mock_cfg
    app.include_router(router)
    return app


def test_create_user_success(mock_cfg):
    client = TestClient(_app(mock_cfg))

    resp = client.post(
        "/api/users",
        json={"email": "User@Example.com", "password": "secret123"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert "id" in body
    assert "created_at" in body
    assert "password_hash" not in body

    stored = client.app.state.users.get_by_email("user@example.com")
    assert stored is not None
    assert stored.password_hash != "secret123"
    assert bcrypt.checkpw(
        b"secret123",
        stored.password_hash.encode("utf-8"),
    )


def test_create_user_rejects_duplicate_email(mock_cfg):
    client = TestClient(_app(mock_cfg))
    payload = {"email": "user@example.com", "password": "secret123"}

    assert client.post("/api/users", json=payload).status_code == 201

    resp = client.post("/api/users", json=payload)

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_create_user_rejects_invalid_email(mock_cfg):
    client = TestClient(_app(mock_cfg))

    resp = client.post(
        "/api/users",
        json={"email": "not-an-email", "password": "secret123"},
    )

    assert resp.status_code == 422


def test_create_user_handles_internal_error(mock_cfg):
    app = _app(mock_cfg)
    broken = UserService()
    app.state.users = broken
    client = TestClient(app)

    def _boom(email: str, password: str):
        raise RuntimeError("boom")

    broken.create_user = _boom  # type: ignore[method-assign]

    resp = client.post(
        "/api/users",
        json={"email": "user@example.com", "password": "secret123"},
    )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to create user"
