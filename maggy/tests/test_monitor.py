"""Tests for MonitorService — background tracker polling."""

from __future__ import annotations

import pytest

from maggy.services.monitor import (
    MonitorConfig,
    MonitorService,
)


@pytest.fixture()
def svc(tmp_path):
    return MonitorService(tmp_path / "monitors.db")


def test_add_and_list(svc):
    """Adding a monitor config makes it listable."""
    cfg = MonitorConfig(project_key="protaige", provider="github")
    svc.add(cfg)
    active = svc.list_active()
    assert len(active) == 1
    assert active[0].project_key == "protaige"


def test_remove(svc):
    """Removing a monitor clears it from active list."""
    svc.add(MonitorConfig(project_key="example-project", provider="asana"))
    svc.remove("example-project")
    assert svc.list_active() == []


def test_is_new_unseen(svc):
    """Unseen event IDs are detected as new."""
    assert svc.is_new("PR-42", "protaige") is True


def test_mark_seen_not_new(svc):
    """After marking seen, event is no longer new."""
    svc.mark_seen("PR-42", "protaige")
    assert svc.is_new("PR-42", "protaige") is False


def test_add_duplicate_updates(svc):
    """Adding same project_key twice updates, not duplicates."""
    svc.add(MonitorConfig(project_key="x", provider="github"))
    svc.add(MonitorConfig(project_key="x", provider="asana"))
    active = svc.list_active()
    assert len(active) == 1
    assert active[0].provider == "asana"


def test_default_interval(svc):
    """Default poll interval is 300 seconds."""
    cfg = MonitorConfig(project_key="p", provider="github")
    svc.add(cfg)
    assert svc.list_active()[0].interval_seconds == 300


def test_status_summary(svc):
    """Status returns dict with counts."""
    svc.add(MonitorConfig(project_key="a", provider="github"))
    svc.add(MonitorConfig(project_key="b", provider="asana"))
    status = svc.status()
    assert status["active"] == 2


@pytest.mark.asyncio()
async def test_poll_github_prs(svc, monkeypatch):
    """Poll detects new GitHub PRs via httpx mock."""
    import httpx

    cfg = MonitorConfig(
        project_key="protaige", provider="github",
        poll_command="alinaqi/AI-Playground",
    )

    class FakeResp:
        status_code = 200
        def json(self):
            return [
                {"number": 1, "title": "Add auth",
                 "html_url": "https://github.com/x/1"},
            ]

    async def fake_get(self, url, **kw):
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    events = await svc.poll(cfg)
    assert len(events) == 1
    assert events[0].title == "Add auth"
