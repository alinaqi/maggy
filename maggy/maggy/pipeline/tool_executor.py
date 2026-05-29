"""Tool executor — sandboxed execution with backup and rollback."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
from maggy.pipeline.tool_schema import TOOL_ALLOWLIST, WRITE_TOOLS, ToolCall

logger = logging.getLogger(__name__)

_MAX_CALLS_PER_ROUND = 10
_BACKUP_DIR = ".maggy-backup"

_HANDLERS = {
    "file_read": "_handle_file_read",
    "grep": "_handle_grep",
    "git_status": "_handle_git_status",
    "git_diff": "_handle_git_diff",
    "git_log": "_handle_git_log",
    "test_run": "_handle_test_run",
    "file_write": "_handle_file_write",
    "file_edit": "_handle_file_edit",
    "git_commit": "_handle_git_commit",
}


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: str


class ToolExecutor:
    def __init__(
        self, sandbox: ToolSandbox, working_dir: str,
        approval_store=None,
    ) -> None:
        self._sandbox = sandbox
        self._root = Path(working_dir)
        self._approval_store = approval_store

    async def execute_round(
        self, calls: list[ToolCall],
    ) -> list[ToolResult]:
        bounded = calls[:_MAX_CALLS_PER_ROUND]
        results: list[ToolResult] = []
        for call in bounded:
            result = await self._execute_one(call)
            results.append(result)
        return results

    async def _execute_one(
        self, call: ToolCall,
    ) -> ToolResult:
        try:
            self._sandbox.validate_tool_call(call)
        except ToolSandboxError as e:
            return ToolResult(call.name, False, str(e))
        handler_name = _HANDLERS.get(call.name)
        if not handler_name:
            return ToolResult(call.name, False, "No handler")
        handler = getattr(self, handler_name)
        try:
            output = await handler(call.params)
            self._notify_approval(call, output, success=True)
            return ToolResult(call.name, True, output)
        except Exception as e:
            self._notify_approval(call, str(e), success=False)
            return ToolResult(call.name, False, str(e))

    def _notify_approval(
        self, call: ToolCall, output: str, success: bool,
    ) -> None:
        if not self._approval_store:
            return
        if call.name not in WRITE_TOOLS:
            return
        try:
            from maggy.services.approval import ApprovalRequest
            status = "approved" if success else "rejected"
            req = ApprovalRequest(
                action=call.name,
                risk="write",
                context=f"{call.name}({call.params}) → {output[:200]}",
                tool_calls=[{"name": call.name, "params": call.params}],
                status=status,
            )
            self._approval_store.save(req)
        except Exception:
            logger.debug("Approval notification failed", exc_info=True)

    def _create_backup(self, path: Path) -> None:
        backup_dir = self._root / _BACKUP_DIR
        backup_dir.mkdir(exist_ok=True)
        if path.exists():
            rel = path.relative_to(self._root)
            dest = backup_dir / str(rel).replace("/", "__")
            shutil.copy2(path, dest)

    def _rollback(self, path: Path) -> None:
        backup_dir = self._root / _BACKUP_DIR
        rel = path.relative_to(self._root)
        src = backup_dir / str(rel).replace("/", "__")
        if src.exists():
            shutil.copy2(src, path)

    def _cleanup_backups(self) -> None:
        backup_dir = self._root / _BACKUP_DIR
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

    async def _handle_file_read(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import file_read
        path = self._sandbox.validate_path(params["path"])
        return await file_read(path)

    async def _handle_grep(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import grep
        path = self._sandbox.validate_path(params["path"])
        return await grep(params["pattern"], path)

    async def _handle_git_status(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import git_status
        return await git_status(self._root)

    async def _handle_git_diff(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import git_diff
        ref = params.get("ref", "HEAD")
        return await git_diff(self._root, ref)

    async def _handle_git_log(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import git_log
        n = params.get("n", 10)
        return await git_log(self._root, n)

    async def _handle_test_run(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import test_run
        timeout = params.get("timeout_s", 120)
        return await test_run(self._root, timeout)

    async def _handle_file_write(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import file_write
        path = self._sandbox.validate_path(params["path"])
        self._create_backup(path)
        result = await file_write(path, params["content"])
        if "error" in result.lower():
            self._rollback(path)
        return result

    async def _handle_file_edit(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import file_edit
        path = self._sandbox.validate_path(params["path"])
        self._create_backup(path)
        result = await file_edit(path, params["old"], params["new"])
        if "error" in result.lower():
            self._rollback(path)
        return result

    async def _handle_git_commit(self, params: dict) -> str:
        from maggy.pipeline.tool_handlers import git_commit
        files = params.get("files")
        return await git_commit(
            self._root, params["message"], files,
        )
