"""Tests for pipeline orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from maggy.pipeline.models import PipelineContext
from maggy.pipeline.orchestrator import ChatPipeline


def _ctx(**kw):
    defaults = dict(
        session_id="sess1", message="hello",
        project_key="proj", working_dir="/tmp",
    )
    defaults.update(kw)
    return PipelineContext(**defaults)


def _mock_backend(name, handles_fn=None, chunks=None):
    b = MagicMock()
    b.name = name
    b.handles = handles_fn or (lambda m: m == name)
    if chunks is None:
        chunks = [
            {"type": "text", "content": "response"},
            {"type": "result", "cost_usd": 0.01,
             "input_tokens": 100, "output_tokens": 50},
        ]

    async def execute(model, message, session, wd, pk):
        for c in chunks:
            yield c

    b.execute = execute
    return b


def _mock_routing(model="kimi", blast=3, task_type="general"):
    from maggy.services.chat_router import RouteDecision
    routing = MagicMock()
    decision = RouteDecision(
        model=model, reason="test", blast=blast, task_type=task_type,
    )
    rc_mock = MagicMock()
    rc_mock.decide = AsyncMock(return_value=decision)
    routing._rc_mock = rc_mock
    routing._decision = decision
    return routing


class TestRun:
    @pytest.mark.asyncio
    async def test_happy_path_yields_chunks(self):
        claude = _mock_backend("claude", lambda m: m == "claude")
        pi = _mock_backend("pi", lambda m: m != "claude")
        log_store = MagicMock()
        log_store.record = MagicMock()
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[claude, pi],
            log_store=log_store,
        )
        session = MagicMock(id="sess1")
        ctx = _ctx()
        chunks = []
        async for c in pipeline.run(ctx, session, model="kimi", blast=3, task_type="general", reason="test"):
            chunks.append(c)
        types = [c["type"] for c in chunks]
        assert "text" in types
        assert "result" in types

    @pytest.mark.asyncio
    async def test_logs_to_store(self):
        pi = _mock_backend("pi", lambda m: True)
        log_store = MagicMock()
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[pi], log_store=log_store,
        )
        session = MagicMock(id="s1")
        async for _ in pipeline.run(_ctx(), session, model="kimi", blast=2, task_type="search", reason="low"):
            pass
        log_store.record.assert_called_once()
        result = log_store.record.call_args[0][0]
        assert result.model == "kimi"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        error_chunks = [{"type": "error", "content": "boom"}]

        async def fail_execute(model, message, session, wd, pk):
            for c in error_chunks:
                yield c

        pi = MagicMock()
        pi.name = "pi"
        pi.handles = lambda m: m != "claude"
        pi.execute = fail_execute

        claude = _mock_backend("claude", lambda m: True)
        log_store = MagicMock()
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[pi, claude],
            log_store=log_store,
        )
        session = MagicMock(id="s1")
        chunks = []
        async for c in pipeline.run(_ctx(), session, model="kimi", blast=3, task_type="general", reason="test"):
            chunks.append(c)
        types = [c["type"] for c in chunks]
        assert "agent_status" in types
        assert "text" in types
        result = log_store.record.call_args[0][0]
        assert result.fallback_used == "claude"

    @pytest.mark.asyncio
    async def test_no_fallback_for_claude(self):
        error_chunks = [{"type": "error", "content": "fail"}]

        async def fail_execute(model, message, session, wd, pk):
            for c in error_chunks:
                yield c

        claude = MagicMock()
        claude.name = "claude"
        claude.handles = lambda m: True
        claude.execute = fail_execute
        log_store = MagicMock()
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[claude], log_store=log_store,
        )
        session = MagicMock(id="s1")
        chunks = []
        async for c in pipeline.run(_ctx(), session, model="claude", blast=5, task_type="general", reason="test"):
            chunks.append(c)
        assert any(c["type"] == "error" for c in chunks)
        result = log_store.record.call_args[0][0]
        assert result.success is False
        assert result.fallback_used == ""


class TestAddBackend:
    def test_add_backend(self):
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[], log_store=MagicMock(),
        )
        b = _mock_backend("executor")
        pipeline.add_backend(b)
        assert len(pipeline._backends) == 1


class TestSelectBackend:
    def test_selects_matching(self):
        claude = _mock_backend("claude", lambda m: m == "claude")
        pi = _mock_backend("pi", lambda m: m != "claude")
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[claude, pi], log_store=MagicMock(),
        )
        assert pipeline._select_backend("kimi").name == "pi"
        assert pipeline._select_backend("claude").name == "claude"

    def test_falls_back_to_first(self):
        claude = _mock_backend("claude", lambda m: False)
        pipeline = ChatPipeline(
            routing=None, budget=None,
            backends=[claude], log_store=MagicMock(),
        )
        assert pipeline._select_backend("unknown").name == "claude"
