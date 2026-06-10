"""Tests for pipeline backend protocol and implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.pipeline.backend import Backend
from maggy.pipeline.backend_claude import ClaudeBackend
from maggy.pipeline.backend_pi import PiBackend


class TestBackendProtocol:
    def test_claude_implements_protocol(self):
        b = ClaudeBackend(MagicMock())
        assert isinstance(b, Backend)

    def test_pi_implements_protocol(self):
        b = PiBackend(MagicMock())
        assert isinstance(b, Backend)


class TestClaudeBackend:
    def test_name(self):
        b = ClaudeBackend(MagicMock())
        assert b.name == "claude"

    def test_handles_claude(self):
        b = ClaudeBackend(MagicMock())
        assert b.handles("claude") is True

    def test_rejects_pi_models(self):
        b = ClaudeBackend(MagicMock())
        assert b.handles("deepseek") is False
        assert b.handles("kimi") is False
        assert b.handles("local") is False

    @pytest.mark.asyncio
    async def test_execute_delegates_to_chat(self):
        chat = MagicMock()
        chunks = [
            {"type": "text", "content": "hello"},
            {"type": "result", "cost_usd": 0.01},
        ]

        async def fake_send(sid, msg):
            for c in chunks:
                yield c

        chat.send = fake_send
        b = ClaudeBackend(chat)
        session = MagicMock(id="sess1")
        collected = []
        async for chunk in b.execute(
            "claude", "hi", session, "/tmp", "proj",
        ):
            collected.append(chunk)
        assert len(collected) == 2
        assert collected[0]["content"] == "hello"


class TestPiBackend:
    def test_name(self):
        b = PiBackend(MagicMock())
        assert b.name == "pi"

    def test_handles_pi_models(self):
        b = PiBackend(MagicMock())
        assert b.handles("deepseek") is True
        assert b.handles("kimi") is True
        assert b.handles("local") is True
        assert b.handles("gemini") is True
        assert b.handles("grok") is True

    def test_rejects_claude(self):
        b = PiBackend(MagicMock())
        assert b.handles("claude") is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        pi = MagicMock()
        result = MagicMock(
            success=True, output="response text",
            cost_usd=0.001, input_tokens=50, output_tokens=30,
        )
        pi.send_prompt = AsyncMock(return_value=result)
        b = PiBackend(pi)
        session = MagicMock()
        collected = []
        async for chunk in b.execute(
            "kimi", "hello", session, "/tmp", "",
        ):
            collected.append(chunk)
        assert any(c["type"] == "text" for c in collected)
        assert any(c["type"] == "result" for c in collected)

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        pi = MagicMock()
        result = MagicMock(
            success=False, error="CLI not found",
            output="", cost_usd=0, input_tokens=0, output_tokens=0,
        )
        pi.send_prompt = AsyncMock(return_value=result)
        b = PiBackend(pi)
        session = MagicMock()
        collected = []
        async for chunk in b.execute(
            "kimi", "hello", session, "/tmp", "",
        ):
            collected.append(chunk)
        assert collected[0]["type"] == "error"
