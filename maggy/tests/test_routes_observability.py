"""Tests for /api/observability endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _app(tmp_path):
    """Build a minimal FastAPI app with observability router."""
    from fastapi import FastAPI
    from maggy.api.routes_observability import router
    from maggy.config import DashboardConfig, MaggyConfig, StorageConfig
    from maggy.observability.collector import ObservabilityCollector

    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        dashboard=DashboardConfig(),
    )
    app = FastAPI()
    app.state.cfg = cfg
    app.state.observability = ObservabilityCollector(tmp_path / "obs.db")
    app.include_router(router)
    return app


def test_get_signals_empty(tmp_path):
    client = TestClient(_app(tmp_path))
    resp = client.get("/api/observability/signals/myproject")
    assert resp.status_code == 200
    assert resp.json() == []


def test_record_and_read(tmp_path):
    client = TestClient(_app(tmp_path))
    body = {
        "project": "webapp",
        "signal_type": "deploy_status",
        "value": 1.0,
    }
    resp = client.post("/api/observability/record", json=body)
    assert resp.status_code == 201

    resp = client.get("/api/observability/signals/webapp")
    signals = resp.json()
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "deploy_status"
