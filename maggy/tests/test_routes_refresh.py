"""Tests for /refresh API endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from maggy.api.routes_refresh import router
from maggy.services.refresh import SessionDigest


def _app(refresh_svc=None, session_store=None, chat=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.refresh = refresh_svc
    app.state.session_store = session_store
    app.state.chat = chat
    cfg = MagicMock()
    cfg.dashboard.auth_mode = "local"
    app.state.cfg = cfg
    return app


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    async def test_returns_digests(self):
        svc = MagicMock()
        svc.refresh.return_value = [
            SessionDigest(
                session_id="abc", cli="claude",
                project="maggy", project_path="/tmp/maggy",
                last_prompt="fix bug", timestamp="123",
                turns=[
                    {"role": "user", "text": "fix bug"},
                    {"role": "assistant", "text": "Fixed it."},
                ],
            ),
        ]
        app = _app(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/refresh")
        assert r.status_code == 200
        data = r.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["project"] == "maggy"
        assert len(data["sessions"][0]["turns"]) == 2

    @pytest.mark.asyncio
    async def test_no_service_returns_empty(self):
        app = _app(refresh_svc=None)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/refresh")
        assert r.status_code == 200
        assert r.json()["sessions"] == []

    @pytest.mark.asyncio
    async def test_limit_param(self):
        svc = MagicMock()
        svc.refresh.return_value = []
        app = _app(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            await c.get("/api/refresh?limit=5")
        svc.refresh.assert_called_once_with(limit=5, project_path=None)

    @pytest.mark.asyncio
    async def test_project_filter(self):
        svc = MagicMock()
        svc.refresh.return_value = []
        app = _app(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            await c.get("/api/refresh?project=/Users/test/chessiega")
        svc.refresh.assert_called_once_with(
            limit=3, project_path="/Users/test/chessiega",
        )


class TestImportEndpoint:
    @pytest.mark.asyncio
    async def test_imports_turns_and_sets_context(self):
        svc = MagicMock()
        svc.refresh.return_value = [
            SessionDigest(
                session_id="abc123", cli="claude",
                project="chess", project_path="/tmp/chess",
                last_prompt="analyze", timestamp="100",
                turns=[
                    {"role": "user", "text": "analyze position"},
                    {"role": "assistant", "text": "White is winning"},
                ],
            ),
        ]
        store = MagicMock()
        mock_session = MagicMock()
        mock_session.history_context = ""
        chat = MagicMock()
        chat.get_session.return_value = mock_session
        app = _app(svc, store, chat)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.post(
                "/api/refresh/import",
                json={"session_id": "abc123", "target_session_id": "t1"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 2
        assert store.append_message.call_count == 2
        assert "analyze position" in mock_session.history_context
        assert "White is winning" in mock_session.history_context

class TestQuickActions:
    @pytest.mark.asyncio
    async def test_returns_default_actions(self):
        app = _app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/quick-actions")
        assert r.status_code == 200
        actions = r.json()["actions"]
        labels = [a["label"] for a in actions]
        assert "Analyze" in labels
        assert "Memory" in labels

    @pytest.mark.asyncio
    async def test_shows_refresh_when_sessions_exist(self):
        svc = MagicMock()
        svc.refresh.return_value = [
            SessionDigest(
                session_id="x", cli="claude",
                project="test", project_path="/tmp/test",
                last_prompt="fix it", timestamp="1",
                turns=[],
            ),
        ]
        app = _app(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get(
                "/api/quick-actions?project_path=/tmp/test",
            )
        actions = r.json()["actions"]
        labels = [a["label"] for a in actions]
        assert "Continue CLI" in labels


class TestImportNoMatch:
    @pytest.mark.asyncio
    async def test_import_no_match(self):
        svc = MagicMock()
        svc.refresh.return_value = []
        store = MagicMock()
        app = _app(svc, store)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.post(
                "/api/refresh/import",
                json={"session_id": "nope", "target_session_id": "t1"},
            )
        assert r.status_code == 200
        assert r.json()["imported"] == 0
        store.append_message.assert_not_called()
