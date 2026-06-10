"""Tests for /api/projects endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from maggy.registry import ProjectRegistry


def _app(mock_cfg):
    """Build a minimal FastAPI app with projects router."""
    from fastapi import FastAPI
    from maggy.api.routes_projects import router

    app = FastAPI()
    app.state.cfg = mock_cfg
    app.state.registry = ProjectRegistry(mock_cfg)
    app.include_router(router)
    return app


def test_list_projects_empty(mock_cfg):
    client = TestClient(_app(mock_cfg))
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_and_list_project(mock_cfg):
    client = TestClient(_app(mock_cfg))
    body = {
        "name": "webapp",
        "repo": "acme/webapp",
        "path": "/tmp/webapp",
    }
    resp = client.post("/api/projects", json=body)
    assert resp.status_code == 201
    assert resp.json()["status"] == "created"

    resp = client.get("/api/projects")
    names = [p["name"] for p in resp.json()]
    assert "webapp" in names


def test_get_project_not_found(mock_cfg):
    client = TestClient(_app(mock_cfg))
    resp = client.get("/api/projects/nonexistent")
    assert resp.status_code == 404


def test_add_duplicate_project(mock_cfg):
    client = TestClient(_app(mock_cfg))
    body = {
        "name": "dup",
        "repo": "acme/dup",
        "path": "/tmp/dup",
    }
    client.post("/api/projects", json=body)
    resp = client.post("/api/projects", json=body)
    assert resp.status_code == 409


def test_delete_project(mock_cfg):
    client = TestClient(_app(mock_cfg))
    body = {
        "name": "to-delete",
        "repo": "acme/td",
        "path": "/tmp/td",
    }
    client.post("/api/projects", json=body)
    resp = client.delete("/api/projects/to-delete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"

    resp = client.get("/api/projects/to-delete")
    assert resp.status_code == 404


def test_get_project_status(mock_cfg, tmp_path):
    client = TestClient(_app(mock_cfg))
    body = {
        "name": "status-proj",
        "repo": "acme/sp",
        "path": str(tmp_path),
    }
    client.post("/api/projects", json=body)
    resp = client.get("/api/projects/status-proj/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "clis" in data
    assert "git" in data
    assert "cortex" in data
    assert isinstance(data["clis"], list)


def test_get_project_status_not_found(mock_cfg):
    client = TestClient(_app(mock_cfg))
    resp = client.get("/api/projects/ghost/status")
    assert resp.status_code == 404
