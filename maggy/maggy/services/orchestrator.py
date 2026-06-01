"""OrchestratorService — parallel team execution via Polyphony containers.

Manages the lifecycle of container teams: decompose tasks into subtasks,
provision isolated workspaces, run agents in Docker containers, collect
results, and feed back to budget/routing/engram.
"""

from __future__ import annotations

import asyncio
import logging
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
from maggy.orchestrator.models import Result, RunSpec, Task

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter
    from maggy.config import MaggyConfig

logger = logging.getLogger(__name__)


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


def route_subtask(
    subtask: Task, image: str = "polyphony-worker:latest",
) -> RunSpec:
    """Build a RunSpec for a subtask. Minimal defaults."""
    return RunSpec(
        task_id=subtask.id,
        agent="claude",
        identity="default",
        workspace="",
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
        self._teams: dict[str, TeamSession] = {}
        self._bg: set[asyncio.Task] = set()

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
        session = TeamSession(task_id=task_id, subtasks=subtasks)
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
        """Run a single subtask in a Docker container."""
        spec = route_subtask(subtask, self._cfg.orchestrator.image)
        try:
            cid = await async_create_container(spec)
            await async_start_container(cid)
            code = await async_wait_container(cid)
            container_logs(cid)  # capture for future log streaming
            await async_remove_container(cid)
            status = "succeeded" if code == 0 else "failed"
        except Exception as exc:
            logger.warning("Container failed for %s: %s", subtask.id, exc)
            return Result(
                task_id=subtask.id, run_spec_id=spec.id,
                agent=spec.agent, status="failed",
            )
        return Result(
            task_id=subtask.id, run_spec_id=spec.id,
            agent=spec.agent, status=status,
        )

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
