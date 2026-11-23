"""Tests for Ollama → Claude API model escalation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from maggy.services.model_escalation import (
    ollama_with_escalation,
    vision_with_escalation,
)


@pytest.fixture
def no_cli_fallbacks():
    """The kimi and deepseek-flash cascade levels are unavailable."""
    with patch(
        "maggy.services.model_escalation._kimi_request",
        new=AsyncMock(return_value=None),
    ) as kimi, patch(
        "maggy.services.model_escalation._deepseek_request",
        new=AsyncMock(return_value=None),
    ) as deepseek:
        yield kimi, deepseek


class TestOllamaWithEscalation:
    """Text classification escalation: ollama → kimi → deepseek → Claude."""

    @pytest.mark.asyncio
    async def test_ollama_success_no_escalation(self):
        with patch(
            "maggy.services.model_escalation._ollama_request",
            new=AsyncMock(return_value="result text"),
        ):
            result = await ollama_with_escalation("classify this")
        assert result == "result text"

    @pytest.mark.asyncio
    async def test_ollama_fail_escalates_to_claude(self, no_cli_fallbacks):
        with patch(
            "maggy.services.model_escalation._ollama_request",
            new=AsyncMock(return_value=None),
        ), patch(
            "maggy.services.model_escalation._claude_request",
            new=AsyncMock(return_value="claude result"),
        ):
            result = await ollama_with_escalation("classify this")
        assert result == "claude result"
        kimi, deepseek = no_cli_fallbacks
        kimi.assert_awaited_once()
        deepseek.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_both_fail_returns_none(self, no_cli_fallbacks):
        with patch(
            "maggy.services.model_escalation._ollama_request",
            new=AsyncMock(return_value=None),
        ), patch(
            "maggy.services.model_escalation._claude_request",
            new=AsyncMock(return_value=None),
        ):
            result = await ollama_with_escalation("classify this")
        assert result is None


class TestVisionWithEscalation:
    """Image analysis escalation."""

    @pytest.mark.asyncio
    async def test_qwen_success(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        chunks = []
        with patch(
            "maggy.services.model_escalation._qwen_vision",
            new=AsyncMock(return_value=[
                {"type": "text", "content": "A button"},
                {"type": "done"},
            ]),
        ):
            async for c in vision_with_escalation(str(img), "review"):
                chunks.append(c)
        texts = [c["content"] for c in chunks if c.get("type") == "text"]
        assert "A button" in texts

    @pytest.mark.asyncio
    async def test_qwen_fail_escalates_to_claude(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        chunks = []
        with patch(
            "maggy.services.model_escalation._qwen_vision",
            new=AsyncMock(return_value=None),
        ), patch(
            "maggy.services.model_escalation._claude_vision",
            new=AsyncMock(return_value="Claude sees a form"),
        ):
            async for c in vision_with_escalation(str(img), "review"):
                chunks.append(c)
        texts = [c.get("content", "") for c in chunks]
        assert any("Claude sees a form" in t for t in texts)

    @pytest.mark.asyncio
    async def test_both_fail_yields_error(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        chunks = []
        with patch(
            "maggy.services.model_escalation._qwen_vision",
            new=AsyncMock(return_value=None),
        ), patch(
            "maggy.services.model_escalation._claude_vision",
            new=AsyncMock(return_value=None),
        ):
            async for c in vision_with_escalation(str(img), "review"):
                chunks.append(c)
        assert any(c.get("type") == "error" for c in chunks)
