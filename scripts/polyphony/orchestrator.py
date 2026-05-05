"""Supervisor loop (§4 orchestrator).

discover -> claim -> route -> provision -> run -> verify -> land
"""

from __future__ import annotations

from pathlib import Path

from .models import (
    AgentProfile, Identity, Result, RunSpec, Task,
)
from .state_machine import transition
from .store import PolyphonyStore


def discover_tasks(store: PolyphonyStore) -> list[Task]:
    """Find tasks in 'discovered' state."""
    return store.list_tasks(state="discovered")


def claim_task(
    task: Task,
    store: PolyphonyStore,
) -> Task:
    """Transition task to 'claimed' and persist."""
    claimed = transition(task, "claimed")
    store.save_task(claimed)
    return claimed


def provision_workspace(
    task: Task,
    base_dir: Path,
    ref: str,
) -> Path:
    """Create workspace for task. Returns path."""
    return _create_ws(task, base_dir, ref)


def run_agent(run_spec: RunSpec) -> Result:
    """Execute agent in container. Returns Result."""
    return _execute_container(run_spec)


def verify_result(result: Result) -> bool:
    """Check if result passes proof-of-work."""
    return result.status == "succeeded"


class Orchestrator:
    """Main supervisor that drives the task lifecycle."""

    def __init__(
        self,
        store: PolyphonyStore,
        agents: list[AgentProfile],
        policy: dict,
        identities: list[Identity] | None = None,
    ):
        self._store = store
        self._agents = agents
        self._policy = policy
        self._identities = identities or []

    def step(self) -> int:
        """Run one orchestration cycle. Returns tasks processed."""
        tasks = discover_tasks(self._store)
        count = 0
        for task in tasks:
            claim_task(task, self._store)
            count += 1
        return count


def _create_ws(
    task: Task,
    base_dir: Path,
    ref: str,
) -> Path:
    """Placeholder for workspace creation. Mockable."""
    from .workspace import create_workspace
    return create_workspace(
        base_dir=base_dir,
        task_id=task.id,
        attempt=1,
        repo_url="",
        ref=ref,
    )


def _execute_container(run_spec: RunSpec) -> Result:
    """Placeholder for container execution. Mockable."""
    return Result(
        task_id=run_spec.task_id,
        run_spec_id=run_spec.id,
        agent=run_spec.agent,
        status="failed",
    )
