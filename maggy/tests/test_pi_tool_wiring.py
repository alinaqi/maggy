"""Tests for Pi backend tool execution wiring."""

from __future__ import annotations

import pytest


class TestPiContextIncludesTools:
    def test_context_mentions_tool_call(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        assert "tool_call" in ctx

    def test_context_lists_available_tools(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        assert "file_read" in ctx
        assert "file_write" in ctx
        assert "grep" in ctx

    def test_context_still_says_autonomous(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        lower = ctx.lower()
        assert "autonomous" in lower or "agent" in lower

    def test_context_still_says_execute(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        assert "execut" in ctx.lower()


class TestExecutorNotifiesApproval:
    @pytest.mark.asyncio
    async def test_write_creates_approval_record(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        from maggy.services.approval import ApprovalStore

        store = ApprovalStore(str(tmp_path / "approvals.db"))
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path), approval_store=store)

        calls = [
            ToolCall("file_write", {"path": "test.py", "content": "x = 1"}),
        ]
        await ex.execute_round(calls)
        history = store.history()
        assert len(history) == 1
        assert history[0].action == "file_write"

    @pytest.mark.asyncio
    async def test_read_does_not_create_approval(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        from maggy.services.approval import ApprovalStore

        (tmp_path / "a.py").write_text("x = 1")
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path), approval_store=store)

        calls = [ToolCall("file_read", {"path": "a.py"})]
        await ex.execute_round(calls)
        history = store.history()
        assert len(history) == 0
