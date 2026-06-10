"""Tests for approval gate — inbox-based review for write operations."""

from __future__ import annotations

import pytest


class TestApprovalRequest:
    def test_creates_request(self):
        from maggy.services.approval import ApprovalRequest
        req = ApprovalRequest(
            action="file_write",
            risk="write",
            context="Writing to src/main.py",
            tool_calls=[{"name": "file_write", "params": {"path": "src/main.py"}}],
        )
        assert req.action == "file_write"
        assert req.status == "pending"
        assert req.id is not None

    def test_auto_generates_id(self):
        from maggy.services.approval import ApprovalRequest
        r1 = ApprovalRequest(action="a", risk="write", context="x")
        r2 = ApprovalRequest(action="b", risk="write", context="y")
        assert r1.id != r2.id


class TestApprovalStore:
    @pytest.fixture
    def store(self, tmp_path):
        from maggy.services.approval import ApprovalStore
        db_path = str(tmp_path / "approvals.db")
        return ApprovalStore(db_path)

    def test_save_and_get(self, store):
        from maggy.services.approval import ApprovalRequest
        req = ApprovalRequest(
            action="file_write", risk="write", context="test",
        )
        store.save(req)
        loaded = store.get(req.id)
        assert loaded is not None
        assert loaded.action == "file_write"
        assert loaded.status == "pending"

    def test_resolve_approve(self, store):
        from maggy.services.approval import ApprovalRequest
        req = ApprovalRequest(
            action="git_commit", risk="write", context="commit",
        )
        store.save(req)
        store.resolve(req.id, "approved", "human")
        loaded = store.get(req.id)
        assert loaded.status == "approved"
        assert loaded.resolved_by == "human"

    def test_resolve_reject(self, store):
        from maggy.services.approval import ApprovalRequest
        req = ApprovalRequest(
            action="file_edit", risk="write", context="edit",
        )
        store.save(req)
        store.resolve(req.id, "rejected", "human")
        loaded = store.get(req.id)
        assert loaded.status == "rejected"

    def test_pending_list(self, store):
        from maggy.services.approval import ApprovalRequest
        r1 = ApprovalRequest(action="a", risk="write", context="x")
        r2 = ApprovalRequest(action="b", risk="write", context="y")
        store.save(r1)
        store.save(r2)
        store.resolve(r1.id, "approved", "human")
        pending = store.pending()
        assert len(pending) == 1
        assert pending[0].id == r2.id

    def test_history(self, store):
        from maggy.services.approval import ApprovalRequest
        r1 = ApprovalRequest(action="a", risk="write", context="x")
        store.save(r1)
        store.resolve(r1.id, "approved", "timeout")
        history = store.history(limit=10)
        assert len(history) == 1
        assert history[0].resolved_by == "timeout"

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent") is None


class TestApprovalGate:
    def test_read_risk_auto_approves(self):
        from maggy.services.approval import ApprovalGate
        gate = ApprovalGate(store=None)
        result = gate.classify_risk("read")
        assert result == "auto"

    def test_write_risk_needs_review(self):
        from maggy.services.approval import ApprovalGate
        gate = ApprovalGate(store=None)
        result = gate.classify_risk("write")
        assert result == "review"
