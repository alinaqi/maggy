"""OrchestratorService — parallel team execution via Polyphony containers.

Manages the lifecycle of container teams: decompose tasks into subtasks,
provision isolated workspaces, run agents in Docker containers, collect
results, and feed back to budget/routing/engram.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from maggy.orchestrator.async_runtime import (
    async_create_container,
    async_start_container,
    async_wait_container,
    async_remove_container,
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
        try:
            if level == IsolationLevel.CONTAINER:
                code = await self._run_container(spec)
            else:
                code = await self._run_local(spec, subtask)
            status = "succeeded" if code == 0 else "failed"
        except Exception as exc:
            logger.warning("Subtask %s failed: %s", subtask.id, exc)
            status = "failed"
        finally:
            if provisioned and session.repo_dir:
                try:
                    cleanup_workspace(level, Path(session.repo_dir), workspace)
                except Exception as exc:
                    logger.warning("Workspace cleanup failed for %s: %s",
                                   session_id, exc)
        return Result(
            task_id=subtask.id, run_spec_id=spec.id,
            agent=spec.agent, status=status,
        )

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
        """Run a subtask locally in its workspace; returns exit code."""
        cmd = self._local_command(subtask)
        proc = await asyncio.to_thread(
            subprocess.run, cmd,
            cwd=spec.workspace or None,
            capture_output=True, text=True, timeout=self._timeout,
        )
        return proc.returncode

    def _local_command(self, subtask: Task) -> list[str]:
        """Build the local agent CLI invocation for a subtask."""
        desc = getattr(subtask, "description", "") or ""
        prompt = f"{subtask.title}\n\n{desc}".strip()
        return [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
        ]

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
