"""Tests for context compactor — message summarization."""

from __future__ import annotations

import pytest

from maggy.services.context_compactor import (
    CompactionResult,
    estimate_tokens,
    should_compact,
)


class TestEstimateTokens:
    def test_empty_list(self):
        assert estimate_tokens([]) == 0

    def test_single_message(self):
        msgs = [{"role": "user", "content": "hello world"}]
        assert estimate_tokens(msgs) > 0

    def test_approximation(self):
        text = "a" * 400
        msgs = [{"role": "user", "content": text}]
        assert estimate_tokens(msgs) == pytest.approx(100, abs=10)


class TestShouldCompact:
    def test_below_threshold_no_compact(self):
        msgs = [{"role": "user", "content": "short"}]
        assert not should_compact(msgs, context_window=200_000)

    def test_above_threshold_compact(self):
        big = "x" * 160_000
        msgs = [{"role": "user", "content": big}]
        assert should_compact(msgs, context_window=40_000)

    def test_threshold_at_80_pct(self):
        content = "a" * 32_800
        msgs = [{"role": "user", "content": content}]
        assert should_compact(msgs, context_window=10_000)


class TestCompact:
    @pytest.mark.asyncio
    async def test_keeps_recent_messages(self):
        from maggy.services.context_compactor import compact
        msgs = [
            {"role": "user", "content": f"msg {i}"}
            for i in range(10)
        ]

        async def fake_summarize(text):
            return "summary of old messages"

        result = await compact(msgs, keep_recent=4, summarizer=fake_summarize)
        assert isinstance(result, CompactionResult)
        assert len(result.messages) == 5
        assert result.messages[0]["role"] == "system"
        assert "summary" in result.messages[0]["content"]
        assert result.messages[-1]["content"] == "msg 9"

    @pytest.mark.asyncio
    async def test_nothing_to_compact(self):
        from maggy.services.context_compactor import compact
        msgs = [{"role": "user", "content": "hi"}]

        async def fake_summarize(text):
            return "summary"

        result = await compact(msgs, keep_recent=6, summarizer=fake_summarize)
        assert result.messages == msgs
        assert result.tokens_saved == 0

    @pytest.mark.asyncio
    async def test_summarizer_failure_passthrough(self):
        from maggy.services.context_compactor import compact
        msgs = [
            {"role": "user", "content": f"msg {i}"}
            for i in range(10)
        ]

        async def broken_summarize(text):
            raise RuntimeError("model down")

        result = await compact(msgs, keep_recent=4, summarizer=broken_summarize)
        assert result.messages == msgs
        assert result.tokens_saved == 0
