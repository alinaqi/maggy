"""Tests for approval REST endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_approval import router
from maggy.services.approval import ApprovalRequest, ApprovalStore


@pytest.fixture
def app(tmp_path):
    app = FastAPI()
    app.include_router(router)
    store = ApprovalStore(str(tmp_path / "approvals.db"))
    app.state.approval_store = store
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestPendingEndpoint:
    def test_empty_pending(self, client):
        resp = client.get("/api/approval/pending")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_returns_pending(self, client, app):
        req = ApprovalRequest(
            action="file_write", risk="write",
            context="Write to main.py",
        )
        app.state.approval_store.save(req)
        resp = client.get("/api/approval/pending")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "file_write"


class TestApproveEndpoint:
    def test_approve(self, client, app):
        req = ApprovalRequest(
            action="file_edit", risk="write", context="Edit",
        )
        app.state.approval_store.save(req)
        resp = client.post(f"/api/approval/{req.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        loaded = app.state.approval_store.get(req.id)
        assert loaded.status == "approved"

    def test_approve_missing_404(self, client):
        resp = client.post("/api/approval/nonexistent/approve")
        assert resp.status_code == 404


class TestRejectEndpoint:
    def test_reject(self, client, app):
        req = ApprovalRequest(
            action="git_commit", risk="write", context="Commit",
        )
        app.state.approval_store.save(req)
        resp = client.post(f"/api/approval/{req.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_missing_404(self, client):
        resp = client.post("/api/approval/nonexistent/reject")
        assert resp.status_code == 404


class TestHistoryEndpoint:
    def test_empty_history(self, client):
        resp = client.get("/api/approval/history")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_returns_resolved(self, client, app):
        req = ApprovalRequest(
            action="file_write", risk="write", context="test",
        )
        app.state.approval_store.save(req)
        app.state.approval_store.resolve(req.id, "approved", "human")
        resp = client.get("/api/approval/history")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["resolved_by"] == "human"


class TestNoStore:
    def test_pending_no_store(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/approval/pending")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
