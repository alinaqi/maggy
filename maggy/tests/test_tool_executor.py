"""Tests for tool executor — sandboxed execution with backup/rollback."""

from __future__ import annotations

import pytest


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_executes_read_tool(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        (tmp_path / "a.py").write_text("x = 1")
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        calls = [ToolCall("file_read", {"path": "a.py"})]
        results = await ex.execute_round(calls)
        assert len(results) == 1
        assert results[0].success is True
        assert "x = 1" in results[0].output

    @pytest.mark.asyncio
    async def test_executes_write_tool(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        calls = [
            ToolCall("file_write", {"path": "new.py", "content": "y = 2"}),
        ]
        results = await ex.execute_round(calls)
        assert results[0].success is True
        assert (tmp_path / "new.py").read_text() == "y = 2"

    @pytest.mark.asyncio
    async def test_rejects_sandbox_violation(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        calls = [
            ToolCall("file_read", {"path": "../../etc/passwd"}),
        ]
        results = await ex.execute_round(calls)
        assert results[0].success is False
        assert "sandbox" in results[0].output.lower()

    @pytest.mark.asyncio
    async def test_limits_calls_per_round(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        calls = [ToolCall("git_status", {})] * 15
        results = await ex.execute_round(calls)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_backup_and_rollback(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        f = tmp_path / "orig.py"
        f.write_text("original")
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        ex._create_backup(f)
        f.write_text("modified")
        ex._rollback(f)
        assert f.read_text() == "original"

    @pytest.mark.asyncio
    async def test_cleanup_backups(self, tmp_path):
        from maggy.pipeline.tool_executor import ToolExecutor
        from maggy.pipeline.tool_sandbox import ToolSandbox
        f = tmp_path / "a.py"
        f.write_text("x")
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        ex._create_backup(f)
        backup_dir = tmp_path / ".maggy-backup"
        assert backup_dir.exists()
        ex._cleanup_backups()
        assert not backup_dir.exists()


class TestToolLoopResult:
    def test_result_dataclass(self):
        from maggy.pipeline.tool_executor import ToolResult
        r = ToolResult(
            tool_name="file_read",
            success=True,
            output="x = 1",
        )
        assert r.tool_name == "file_read"
        assert r.success is True
