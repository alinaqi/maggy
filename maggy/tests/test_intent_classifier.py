"""Tests for semantic intent classification via local model."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from maggy.services.intent_classifier import (
    KNOWN_TYPES,
    classify_blast,
    classify_intent,
    _parse_blast,
    _parse_response,
)


def test_parse_valid_type():
    """Valid JSON type is returned as-is."""
    assert _parse_response('{"type": "review"}') == "review"


def test_parse_unknown_falls_back():
    """Unknown type falls back to 'general'."""
    assert _parse_response('{"type": "banana"}') == "general"


def test_parse_garbage_falls_back():
    """Non-JSON falls back to 'general'."""
    assert _parse_response("not json at all") == "general"


def test_known_types_complete():
    """KNOWN_TYPES includes the expected categories."""
    for t in ("review", "security", "search", "docs", "tests", "frontend"):
        assert t in KNOWN_TYPES


@pytest.mark.asyncio
async def test_classify_returns_model_answer():
    """When Ollama responds, use its classification."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "message": {"content": '{"type": "review"}'},
    }
    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_return(fake_resp)
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("review the auth code")
    assert result == "review"


@pytest.mark.asyncio
async def test_classify_fallback_on_error():
    """When Ollama is down, fall back to keyword matching."""
    import httpx

    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_raise(httpx.ConnectError("down"))
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("fix the login bug")
    assert result == "general"


@pytest.mark.asyncio
async def test_classify_timeout_fallback():
    """Timeout falls back to keyword matching."""
    import httpx

    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_raise(httpx.ReadTimeout("slow"))
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("review the PR")
    # keyword fallback: "review" is in TYPE_KEYWORDS
    assert result == "review"


# ── Blast score parsing ──────────────────────────────────────────────


def test_parse_blast_valid():
    """Valid JSON blast score is returned."""
    assert _parse_blast('{"blast": 7}') == 7


def test_parse_blast_clamped_high():
    """Blast > 10 is clamped to 10."""
    assert _parse_blast('{"blast": 15}') == 10


def test_parse_blast_clamped_low():
    """Blast < 1 is clamped to 1."""
    assert _parse_blast('{"blast": 0}') == 1


def test_parse_blast_garbage_returns_none():
    """Non-JSON returns None (triggers fallback)."""
    assert _parse_blast("not json") is None


@pytest.mark.asyncio
async def test_classify_blast_returns_model_score():
    """When Ollama responds, use its blast score."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "message": {"content": '{"blast": 8}'},
    }
    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_return(fake_resp)
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_blast("redesign the auth system")
    assert result == 8


@pytest.mark.asyncio
async def test_classify_blast_fallback_on_error():
    """When Ollama is down, fall back to keyword estimation."""
    import httpx

    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_raise(httpx.ConnectError("down"))
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_blast("fix typo in readme")
    assert isinstance(result, int)
    assert 1 <= result <= 10


# ── Helpers ──────────────────────────────────────────────────────────


def _async_return(value):
    """Create an async function that returns value."""
    async def _inner(*args, **kwargs):
        return value
    return _inner


def _async_raise(exc):
    """Create an async function that raises exc."""
    async def _inner(*args, **kwargs):
        raise exc
    return _inner
