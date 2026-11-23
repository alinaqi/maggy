"""OrchestratorService — parallel team execution via Polyphony containers.

Manages the lifecycle of container teams: decompose tasks into subtasks,
provision isolated workspaces, run agents in Docker containers, collect
results, and feed back to budget/routing/engram.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from maggy.orchestrator.async_runtime import (
    async_create_container,
    async_remove_container,
    async_start_container,
    async_wait_container,
    container_logs,
)
from maggy.orchestrator.decomposer import decompose_task
from maggy.orchestrator.isolation import (
    IsolationLevel,
    cleanup_workspace,
    detect_capabilities,
    provision_workspace,
)
from maggy.orchestrator.models import Result, RunSpec, Task
from maggy.services.workspace_guard import safe_merge

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter
    from maggy.config import MaggyConfig

logger = logging.getLogger(__name__)

# Maps config `isolation:` values to a concrete strategy. "auto" probes the
# host (docker > git worktree > lock-only). Aliases keep config forgiving.
_ISOLATION_ALIASES = {
    "container": IsolationLevel.CONTAINER,
    "docker": IsolationLevel.CONTAINER,
    "worktree": IsolationLevel.WORKTREE,
    "git": IsolationLevel.WORKTREE,
    "local": IsolationLevel.LOCK_ONLY,
    "lock_only": IsolationLevel.LOCK_ONLY,
    "none": IsolationLevel.LOCK_ONLY,
}


def _resolve_isolation(value: str) -> IsolationLevel:
    """Resolve the configured isolation string to an IsolationLevel."""
    v = (value or "auto").strip().lower()
    if v == "auto":
        return detect_capabilities()
    return _ISOLATION_ALIASES.get(v, detect_capabilities())


def _team_id() -> str:
    return f"team-{uuid.uuid4().hex[:8]}"


@dataclass
class TeamSession:
    """Tracks a parallel execution team."""

    team_id: str = field(default_factory=_team_id)
    task_id: str = ""
    subtasks: list[Task] = field(default_factory=list)
    results: list[Result] = field(default_factory=list)
    status: str = "running"
    repo_dir: str | None = None


def route_subtask(
    subtask: Task,
    image: str = "polyphony-worker:latest",
    workspace: str = "",
) -> RunSpec:
    """Build a RunSpec for a subtask. Minimal defaults."""
    return RunSpec(
        task_id=subtask.id,
        agent="claude",
        identity="default",
        workspace=workspace,
        image=image,
    )


class OrchestratorService:
    """Manages parallel container teams."""

    def __init__(self, cfg: "MaggyConfig", pi: "PiAdapter | None" = None) -> None:
        self._cfg = cfg
        self._pi = pi
        orch = cfg.orchestrator
        self._max = orch.max_concurrent
        self._ws_root = Path(orch.workspace_root).expanduser()
        self._timeout = orch.container_timeout
        self._isolation = _resolve_isolation(orch.isolation)
        self._teams: dict[str, TeamSession] = {}
        self._bg: set[asyncio.Task] = set()

    def _resolve_repo(self, subtasks: list[Task]) -> str | None:
        """Pick the source repo for a team from configured codebases."""
        cbs = getattr(self._cfg, "codebases", None) or []
        if not cbs:
            return None
        try:
            from maggy.services.executor_helpers import resolve_working_dir
            ref = subtasks[0] if subtasks else None
            return resolve_working_dir(self._cfg, None, ref)
        except Exception:
            return str(Path(cbs[0].path).expanduser().resolve())

    async def decompose(self, title: str, desc: str) -> list[Task]:
        """Split a task into subtasks via LLM decomposition."""
        if not self._pi:
            from maggy.adapters.pi import PiAdapter
            self._pi = PiAdapter()
        return await decompose_task(self._pi, title, desc)

    async def spawn_team(
        self, task_id: str, subtasks: list[Task],
    ) -> TeamSession:
        """Create a team and launch containers in background."""
        session = TeamSession(
            task_id=task_id, subtasks=subtasks,
            repo_dir=self._resolve_repo(subtasks),
        )
        self._teams[session.team_id] = session
        bg = asyncio.create_task(self._run_team(session))
        self._bg.add(bg)
        bg.add_done_callback(self._bg.discard)
        return session

    async def _run_team(self, session: TeamSession) -> None:
        """Run all subtasks in parallel, collect results."""
        try:
            coros = [self._run_one(st, session) for st in session.subtasks]
            session.results = await asyncio.gather(*coros)
            ok = all(r.status == "succeeded" for r in session.results)
            session.status = "completed" if ok else "partial"
        except Exception:
            logger.exception("Team %s failed", session.team_id)
            session.status = "failed"

    async def _run_one(
        self, subtask: Task, session: TeamSession,
    ) -> Result:
        """Run a subtask in its isolated workspace (container or local)."""
        level = self._isolation
        session_id = f"{session.team_id}-{subtask.id[:8]}"
        workspace, provisioned = self._provision(level, session.repo_dir, session_id)
        spec = route_subtask(subtask, self._cfg.orchestrator.image, workspace)
        status = await self._execute(level, spec, subtask)
        result = Result(
            task_id=subtask.id, run_spec_id=spec.id,
            agent=spec.agent, status=status,
        )
        if provisioned and session.repo_dir:
            self._settle(Path(session.repo_dir), workspace, result)
        return result

    async def _execute(
        self, level: IsolationLevel, spec: RunSpec, subtask: Task,
    ) -> str:
        """Run the agent; return "succeeded" or "failed"."""
        try:
            if level == IsolationLevel.CONTAINER:
                code = await self._run_container(spec)
            else:
                code = await self._run_local(spec, subtask)
            return "succeeded" if code == 0 else "failed"
        except Exception as exc:  # noqa: BLE001 - any agent error fails the subtask
            logger.warning("Subtask %s failed: %s", subtask.id, exc)
            return "failed"

    def _settle(self, repo: Path, workspace: str, result: Result) -> None:
        """Merge a successful workspace and clean it; otherwise keep it."""
        ok = result.status == "succeeded"
        if ok and safe_merge(repo, Path(workspace)):
            try:
                cleanup_workspace(self._isolation, repo, workspace)
            except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
                logger.warning("Workspace cleanup failed for %s: %s",
                               workspace, exc)
            return
        result.status = "failed"
        result.artifacts["workspace"] = workspace
        logger.warning("Keeping unmerged subtask workspace %s", workspace)

    def _provision(
        self, level: IsolationLevel, repo_dir: str | None, session_id: str,
    ) -> tuple[str, bool]:
        """Provision a workspace. Returns (path, was_isolated_worktree)."""
        if not repo_dir:
            return "", False
        try:
            ws = provision_workspace(
                level, Path(repo_dir), session_id, self._ws_root,
            )
            return ws, ws != str(repo_dir)
        except Exception as exc:
            logger.warning("Provision failed for %s (%s); using repo dir",
                           session_id, exc)
            return repo_dir, False

    async def _run_container(self, spec: RunSpec) -> int:
        """Run a subtask inside a Docker container; returns exit code."""
        cid = await async_create_container(spec)
        await async_start_container(cid)
        code = await async_wait_container(cid)
        container_logs(cid)  # capture for future log streaming
        await async_remove_container(cid)
        return code

    async def _run_local(self, spec: RunSpec, subtask: Task) -> int:
        """Run a subtask locally in its workspace; returns exit code.

        Refuses unless a sandbox wrapper is configured: a non-container
        agent run would otherwise have full host access. The agent is
        invoked WITHOUT --dangerously-skip-permissions, so its own
        permission policy still applies.
        """
        sandbox = (self._cfg.orchestrator.local_sandbox or "").strip()
        if not sandbox:
            raise PermissionError(
                "Local (non-container) execution requires "
                "orchestrator.local_sandbox (e.g. firejail/bwrap); "
                "refusing to run an unsandboxed agent."
            )
        cmd = self._local_command(subtask, sandbox)
        proc = await asyncio.to_thread(
            subprocess.run, cmd,
            cwd=spec.workspace or None,
            capture_output=True, text=True, timeout=self._timeout,
        )
        return proc.returncode

    def _local_command(self, subtask: Task, sandbox: str) -> list[str]:
        """Build the sandboxed local agent CLI invocation for a subtask."""
        desc = getattr(subtask, "description", "") or ""
        prompt = f"{subtask.title}\n\n{desc}".strip()
        return [*shlex.split(sandbox), "claude", "-p", prompt]

    async def cancel_team(self, team_id: str) -> None:
        """Cancel a running team."""
        session = self._teams.get(team_id)
        if session:
            session.status = "cancelled"

    def get_team(self, team_id: str) -> TeamSession | None:
        """Get team by ID."""
        return self._teams.get(team_id)

    def list_teams(self) -> list[TeamSession]:
        """List all team sessions."""
        return list(self._teams.values())
