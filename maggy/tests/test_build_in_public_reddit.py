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
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self.post = AsyncMock(return_value=resp)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


# ── credential resolution (env → ideaminer) ────────────────────────────

def test_reddit_cred_prefers_env(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "from-env")
    assert social_api.reddit_cred("REDDIT_CLIENT_ID") == "from-env"


def test_reddit_cred_falls_back_to_ideaminer(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    social_api._ideaminer_env_cache = {"REDDIT_CLIENT_ID": "from-ideaminer"}
    try:
        assert social_api.reddit_cred("REDDIT_CLIENT_ID") == "from-ideaminer"
    finally:
        social_api._ideaminer_env_cache = None


# ── OAuth grant selection ──────────────────────────────────────────────

def test_grant_uses_refresh_token(monkeypatch):
    monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "rt")
    g = social_api.SocialMonitor._reddit_grant()
    assert g["grant_type"] == "refresh_token"


def test_grant_uses_password(monkeypatch):
    monkeypatch.delenv("REDDIT_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("REDDIT_USERNAME", "u")
    monkeypatch.setenv("REDDIT_PASSWORD", "p")
    social_api._ideaminer_env_cache = {}
    try:
        g = social_api.SocialMonitor._reddit_grant()
        assert g["grant_type"] == "password" and g["username"] == "u"
    finally:
        social_api._ideaminer_env_cache = None


def test_grant_empty_without_creds(monkeypatch):
    for k in ("REDDIT_REFRESH_TOKEN", "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    social_api._ideaminer_env_cache = {}
    try:
        assert social_api.SocialMonitor._reddit_grant() == {}
    finally:
        social_api._ideaminer_env_cache = None


# ── reddit_post ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reddit_post_success_returns_id(monkeypatch):
    monkeypatch.setenv("REDDIT_REFRESH_TOKEN", "rt")
    m = social_api.SocialMonitor()
    m._get_reddit_access_token = AsyncMock(return_value="tok")
    client = _FakeClient(_FakeResp(200, {"json": {"errors": [], "data": {"name": "t3_zzz"}}}))
    with patch.object(social_api.httpx, "AsyncClient", return_value=client):
        post_id = await m.reddit_post("buildinpublic", "Shipped X", "body")
    assert post_id == "t3_zzz"
    assert client.post.call_args.args[0].endswith("/api/submit")
    assert client.post.call_args.kwargs["data"]["sr"] == "buildinpublic"


@pytest.mark.asyncio
async def test_reddit_post_no_write_creds(monkeypatch):
    for k in ("REDDIT_REFRESH_TOKEN", "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    social_api._ideaminer_env_cache = {}
    try:
        m = social_api.SocialMonitor()
        assert await m.reddit_post("buildinpublic", "t", "b") == ""
    finally:
        social_api._ideaminer_env_cache = None


# ── ScheduledPost + strategy title ─────────────────────────────────────

def test_scheduled_post_has_title():
    assert plugin.ScheduledPost(channel="reddit", title="T").title == "T"
    assert plugin.ScheduledPost().title == ""


def test_plan_sets_reddit_title():
    strat = plugin.ContentStrategy({"channels": {"reddit": {"max_chars": 8000}}})
    posts = strat.plan("on_feature_shipped", {"what": "Auth revamp"},
                       {"reddit": "We rebuilt auth.\nDetails."})
    reddit = [p for p in posts if p.channel == "reddit"]
    assert reddit and reddit[0].title == "Auth revamp"


# ── autonomous subreddit + routing ─────────────────────────────────────

def test_subreddit_default_is_autonomous():
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {}}}
    assert obj._resolve_reddit_subreddit() == "buildinpublic"


def test_subreddit_explicit_override():
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {"subreddit": "r/SideProject/"}}}
    assert obj._resolve_reddit_subreddit() == "SideProject"


@pytest.mark.asyncio
async def test_submit_reddit_applies_voice_and_tracks(tmp_path, monkeypatch):
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {"subreddit": "ClaudeCode"}},
                   "voice": {"no_em_dash": True, "strip_markdown": True,
                             "typos": {"enabled": False}}}
    obj._posts_today = 0
    obj._log_post = MagicMock()
    obj._redact = lambda x: x
    monkeypatch.setattr(obj, "_reddit_posts_path",
                        lambda: tmp_path / "reddit-posts.json")
    monitor = MagicMock()
    monitor.reddit_post = AsyncMock(return_value="t3_abc")
    with patch.object(social_api, "SocialMonitor", return_value=monitor):
        await obj._submit_reddit({"channel": "reddit",
                                  "title": "Shipped",
                                  "text": "**bold**—done"})
    # voice applied: no markdown, no em-dash
    _, kwargs = monitor.reddit_post.call_args
    args = monitor.reddit_post.call_args.args
    assert "**" not in args[2] and "—" not in args[2]
    # tracked for reply monitoring
    assert obj._posts_today == 1
    tracked = obj._load_reddit_posts()
    assert tracked and tracked[0]["id"] == "t3_abc"


# ── reply agent ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_reddit_replies_skips_self_and_replies_once(tmp_path, monkeypatch):
    monkeypatch.setenv("REDDIT_USERNAME", "naxmax2019")
    social_api._ideaminer_env_cache = {}
    obj = object.__new__(plugin.BuildInPublic)
    obj._config = {"channels": {"reddit": {}}, "voice": {"typos": {"enabled": False}}}
    obj._redact = lambda x: x
    monkeypatch.setattr(obj, "_reddit_posts_path",
                        lambda: tmp_path / "p.json")
    obj._save_reddit_posts([{"id": "t3_x", "subreddit": "ClaudeCode", "replied": []}])
    obj._generate_reply = lambda body, sr: "thanks for trying it"
    monitor = MagicMock()
    monitor.reddit_post_comments = AsyncMock(return_value=[
        {"id": "c1", "fullname": "t1_c1", "author": "someone", "body": "nice tool"},
        {"id": "c2", "fullname": "t1_c2", "author": "naxmax2019", "body": "my own"},
    ])
    monitor.reddit_comment = AsyncMock(return_value=True)
    try:
        with patch.object(social_api, "SocialMonitor", return_value=monitor):
            n = await obj.check_reddit_replies()
    finally:
        social_api._ideaminer_env_cache = None
    assert n == 1  # replied to c1, skipped own c2
    monitor.reddit_comment.assert_awaited_once()
    assert monitor.reddit_comment.call_args.args[0] == "t1_c1"
    # second run does not re-reply
    monitor.reddit_comment.reset_mock()
    with patch.object(social_api, "SocialMonitor", return_value=monitor):
        n2 = await obj.check_reddit_replies()
    assert n2 == 0
    monitor.reddit_comment.assert_not_awaited()
