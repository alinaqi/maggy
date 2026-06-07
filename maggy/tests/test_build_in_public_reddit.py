"""Tests for the Reddit publishing channel in build-in-public."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

_BIP = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "build-in-public"


def _load(modname: str, filename: str):
    """Load a hyphenated-plugin module under its runtime package name."""
    pkg = "maggy.plugins.build_in_public"
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [str(_BIP)]
        sys.modules[pkg] = m
    full = f"{pkg}.{modname}"
    spec = importlib.util.spec_from_file_location(full, _BIP / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


social_api = _load("social_api", "social_api.py")
plugin = _load("plugin", "plugin.py")


class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {"json": {"errors": []}}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp
        self.post = AsyncMock(return_value=resp)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


# ── reddit_submit ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reddit_submit_success(monkeypatch):
    monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "rt")
    m = social_api.SocialMonitor()
    m._get_reddit_access_token = AsyncMock(return_value="tok")
    client = _FakeClient(_FakeResp(200, {"json": {"errors": []}}))
    with patch.object(social_api.httpx, "AsyncClient", return_value=client):
        ok = await m.reddit_submit("buildinpublic", "Shipped X", "body text")
    assert ok is True
    args, kwargs = client.post.call_args
    assert args[0].endswith("/api/submit")
    assert kwargs["data"]["sr"] == "buildinpublic"
    assert kwargs["data"]["kind"] == "self"


@pytest.mark.asyncio
async def test_reddit_submit_no_token(monkeypatch):
    monkeypatch.delenv("REDDIT_REFRESH_TOKEN", raising=False)
    m = social_api.SocialMonitor()
    assert await m.reddit_submit("buildinpublic", "t", "b") is False


@pytest.mark.asyncio
async def test_reddit_submit_missing_subreddit(monkeypatch):
    monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "rt")
    m = social_api.SocialMonitor()
    assert await m.reddit_submit("", "t", "b") is False


@pytest.mark.asyncio
async def test_reddit_submit_api_errors(monkeypatch):
    monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "rt")
    m = social_api.SocialMonitor()
    m._get_reddit_access_token = AsyncMock(return_value="tok")
    client = _FakeClient(_FakeResp(200, {"json": {"errors": [["RATELIMIT", "slow down"]]}}))
    with patch.object(social_api.httpx, "AsyncClient", return_value=client):
        assert await m.reddit_submit("buildinpublic", "t", "b") is False


# ── ScheduledPost + strategy title ─────────────────────────────────────

def test_scheduled_post_has_title():
    p = plugin.ScheduledPost(channel="reddit", text="hi", title="My Title")
    assert p.title == "My Title"
    assert plugin.ScheduledPost().title == ""


def test_plan_sets_reddit_title():
    cfg = {"channels": {"reddit": {"max_chars": 8000}}}
    strat = plugin.ContentStrategy(cfg)
    posts = strat.plan("on_feature_shipped",
                       {"what": "Auth revamp"},
                       {"reddit": "We rebuilt auth.\nDetails follow."})
    reddit = [p for p in posts if p.channel == "reddit"]
    assert reddit and reddit[0].title == "Auth revamp"


# ── _submit_reddit routing ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_reddit_calls_monitor():
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {"subreddit": "buildinpublic"}}}
    obj._posts_today = 0
    obj._log_post = MagicMock()
    fake_monitor = MagicMock()
    fake_monitor.reddit_submit = AsyncMock(return_value=True)
    with patch.object(social_api, "SocialMonitor", return_value=fake_monitor):
        await obj._submit_reddit({"channel": "reddit", "title": "T", "text": "B"})
    fake_monitor.reddit_submit.assert_awaited_once_with("buildinpublic", "T", "B")
    assert obj._posts_today == 1


@pytest.mark.asyncio
async def test_submit_reddit_skips_without_subreddit():
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {"subreddit": ""}}}
    obj._posts_today = 0
    obj._log_post = MagicMock()
    await obj._submit_reddit({"channel": "reddit", "text": "B"})
    obj._log_post.assert_called_once()
    assert obj._posts_today == 0
