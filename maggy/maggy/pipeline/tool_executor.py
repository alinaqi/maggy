"""Tool executor — sandboxed execution with backup and rollback."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
from maggy.pipeline.tool_schema import WRITE_TOOLS, ToolCall

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
        approval_store=None, runner=None,
    ) -> None:
        self._sandbox = sandbox
        self._root = Path(working_dir)
        self._approval_store = approval_store
        # When set (ContainerToolRunner), file/git/shell ops run INSIDE a
        # workspace-mounted container instead of on the host. This is the
        # default isolation for the autonomous path (T2-B).
        self._runner = runner

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
        try:
            if self._runner is not None:
                output = self._run_in_container(call)
            else:
                handler_name = _HANDLERS.get(call.name)
                if not handler_name:
                    return ToolResult(call.name, False, "No handler")
                output = await getattr(self, handler_name)(call.params)
            self._notify_approval(call, output, success=True)
            return ToolResult(call.name, True, output)
        except Exception as e:
            self._notify_approval(call, str(e), success=False)
            return ToolResult(call.name, False, str(e))

    # ── Container execution path (default isolation) ────────────────────

    def _rel(self, path_param: str) -> str:
        """Validate a path and return it relative to the workspace root."""
        abs_path = self._sandbox.validate_path(path_param)
        return str(Path(abs_path).resolve().relative_to(self._root.resolve()))

    def _run_in_container(self, call: ToolCall) -> str:
        """Dispatch a tool call to ops inside the workspace container."""
        from maggy.pipeline.tool_handlers import _detect_test_command
        r = self._runner
        p = call.params
        name = call.name
        if name == "file_read":
            return r.read_file(self._rel(p["path"]))
        if name == "grep":
            rc, out = r.exec(["grep", "-rn", "--", p["pattern"], self._rel(p["path"])])
            return out
        if name == "git_status":
            return r.exec(["git", "status", "--short"])[1]
        if name == "git_diff":
            return r.exec(["git", "diff", p.get("ref", "HEAD")])[1]
        if name == "git_log":
            return r.exec(["git", "log", "--oneline", "-n", str(p.get("n", 10))])[1]
        if name == "test_run":
            cmd = _detect_test_command(self._root)
            if not cmd:
                return "Error: no test command detected"
            return r.run_shell(cmd, timeout=p.get("timeout_s", 120))[1][-5000:]
        if name == "file_write":
            return r.write_file(self._rel(p["path"]), p["content"])
        if name == "file_edit":
            rel = self._rel(p["path"])
            content = r.read_file(rel)
            if p["old"] not in content:
                return "error: old text not found"
            return r.write_file(rel, content.replace(p["old"], p["new"], 1))
        if name == "git_commit":
            files = p.get("files")
            if files:
                r.exec(["git", "add", *[self._rel(f) for f in files]])
            else:
                r.exec(["git", "add", "-A"])
            return r.exec(["git", "commit", "-m", p["message"]])[1]
        return "No handler"

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

    def close(self) -> None:
        """Tear down the container (if any) and remove host backups."""
        if self._runner is not None:
            try:
                self._runner.close()
            except Exception:
                logger.debug("runner close failed", exc_info=True)
        self._cleanup_backups()

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


def build_tool_executor(
    sandbox: ToolSandbox, working_dir: str,
    approval_store=None, isolation: str = "auto",
) -> ToolExecutor:
    """Build a ToolExecutor with the chosen isolation (T2-B).

    isolation:
      "container" — require Docker; raise if it can't start (fail closed).
      "auto"      — container when Docker is available, else host sandbox.
      "process"   — legacy host path-sandbox (deprecated, least safe).
    """
    from maggy.pipeline.container_runner import (
        ContainerToolRunner,
        docker_available,
    )
    runner = None
    if isolation == "container" or (isolation == "auto" and docker_available()):
        runner = ContainerToolRunner(working_dir)
        try:
            runner.start()
        except Exception as e:
            if isolation == "container":
                raise
            logger.warning(
                "container isolation unavailable (%s); host sandbox fallback", e,
            )
            runner = None
    if runner is None and isolation != "process":
        logger.warning(
            "autonomous pipeline running on the host sandbox (no container "
            "isolation) — deprecated; set up Docker for full containment",
        )
    return ToolExecutor(sandbox, working_dir, approval_store, runner=runner)
