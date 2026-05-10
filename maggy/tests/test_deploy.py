"""Tests for deploy service — session management."""

from __future__ import annotations

from maggy.deploy import DeployService, DeploySession


class TestDeployService:
    def test_create_session(self):
        svc = DeployService()
        session = svc.create_session("myapp", "main")
        assert session.project == "myapp"
        assert session.branch == "main"
        assert session.status == "building"

    def test_get_session(self):
        svc = DeployService()
        session = svc.create_session("myapp", "feat")
        result = svc.get_session(session.session_id)
        assert result is not None
        assert result.branch == "feat"

    def test_get_missing_session(self):
        svc = DeployService()
        assert svc.get_session("nonexistent") is None

    def test_list_sessions(self):
        svc = DeployService()
        svc.create_session("app1", "main")
        svc.create_session("app2", "dev")
        sessions = svc.list_sessions()
        assert len(sessions) == 2

    def test_update_status(self):
        svc = DeployService()
        session = svc.create_session("myapp", "main")
        updated = svc.update_status(
            session.session_id, "live",
            url="https://preview.vercel.app",
        )
        assert updated.status == "live"
        assert updated.url == "https://preview.vercel.app"

    def test_update_missing_returns_none(self):
        svc = DeployService()
        assert svc.update_status("nope", "live") is None

    def test_teardown(self):
        svc = DeployService()
        session = svc.create_session("myapp", "main")
        assert svc.teardown(session.session_id)
        assert svc.get_session(session.session_id) is None

    def test_teardown_missing(self):
        svc = DeployService()
        assert not svc.teardown("nonexistent")
