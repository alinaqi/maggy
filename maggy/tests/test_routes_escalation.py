"""Tests for /api/escalations endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _app(tmp_path):
    """Build a minimal FastAPI app with escalation router."""
    from fastapi import FastAPI
    from maggy.api.routes_escalation import router
    from maggy.config import DashboardConfig, MaggyConfig, StorageConfig
    from maggy.escalation.protocol import Escalator

    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        dashboard=DashboardConfig(),
    )
    app = FastAPI()
    app.state.cfg = cfg
    app.state.escalator = Escalator(tmp_path / "esc.db")
    app.include_router(router)
    return app


def test_list_pending_empty(tmp_path):
    client = TestClient(_app(tmp_path))
    resp = client.get("/api/escalations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_list(tmp_path):
    client = TestClient(_app(tmp_path))
    body = {
        "session_id": "sess-1",
        "reason": "test failure",
        "context": {"task_id": "T-1"},
    }
    resp = client.post("/api/escalations", json=body)
    assert resp.status_code == 201
    esc_id = resp.json()["id"]

    resp = client.get("/api/escalations")
    ids = [e["id"] for e in resp.json()]
    assert esc_id in ids


def test_resolve_escalation(tmp_path):
    client = TestClient(_app(tmp_path))
    body = {
        "session_id": "sess-2",
        "reason": "stuck",
        "context": {},
    }
    resp = client.post("/api/escalations", json=body)
    esc_id = resp.json()["id"]

    resp = client.post(
        f"/api/escalations/{esc_id}/resolve",
        json={"guidance": "retry with claude"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    resp = client.get("/api/escalations")
    assert resp.json() == []


def test_resolve_not_found(tmp_path):
    client = TestClient(_app(tmp_path))
    resp = client.post(
        "/api/escalations/bad-id/resolve",
        json={"guidance": "n/a"},
    )
    assert resp.status_code == 404
