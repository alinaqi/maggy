"""Run replay tasks through the full worker pipeline per agent (RFC §2.3, Phase 2 exit).

Offline (default): fake CLIs replay recorded output via the shipped adapters; the fakes are
maggy's own scripts, so host execution is allowed for them. Live (`live=True`): the real
CLIs on PATH, under the personal profile's fail-closed launch policy and per-run budget.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from maggy.harness.errors import HarnessConfigError
from maggy.harness.loader import resolve_profile
from maggy.harness.schema import HarnessProfile
from maggy.worker.adapter_loader import load_adapter
from maggy.worker.assemble import default_state_dir
from maggy.worker.git_ops import GitError, run_git
from maggy.worker.launch import Refused, resolve_launch
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.replay.fake import write_fake_bin
from maggy.worker.replay.report import ReplayReport, ReplayRow, refused_row, result_row
from maggy.worker.replay.tasks import (ReplayTask, check_commands, load_tasks, materialize,
                                       replay_prompt, write_accept)
from maggy.worker.worktree import create_attempt_worktree

PERMISSIONS = {"read_only": {"write": False, "network": False, "shell": False},
               "workspace": {"write": "workspace", "network": False, "shell": "allowlist"}}


@dataclass(frozen=True)
class ReplayOptions:
    agents: list[str]
    tasks: list[str]
    work_dir: Path
    live: bool = False
    state_dir: Path | None = None
    budget_usd: float = 0.25
    deadline_s: int = 300
    models: dict[str, str] = field(default_factory=dict)


def run_replay(opts: ReplayOptions) -> ReplayReport:
    """One row per task x agent (task-major); KeyError for an unknown task."""
    tasks = load_tasks(opts.tasks)
    personal = resolve_profile().profile
    rows = [_row(opts, personal, (task, agent)) for task in tasks for agent in opts.agents]
    return ReplayReport(mode="live" if opts.live else "offline", work_dir=opts.work_dir,
                        rows=rows)


def _row(opts: ReplayOptions, personal: HarnessProfile, case: tuple[ReplayTask, str]) -> ReplayRow:
    task, agent = case
    try:
        return result_row(task, run_attempt(_attempt(opts, personal, case)))
    except (Refused, HarnessConfigError, GitError, KeyError) as exc:
        return refused_row(task, agent, str(exc))


def _attempt(opts: ReplayOptions, personal: HarnessProfile,
             case: tuple[ReplayTask, str]) -> Attempt:
    task, agent = case
    case_dir = opts.work_dir / f"{task.id}-{agent}"
    profile = _profile(opts, personal, write_accept(task, case_dir / "accept"))
    adapter = load_adapter(agent)
    spec = _spec(opts, task, (agent, materialize(task, case_dir / "repo")))
    resolve_launch(adapter, profile, spec.permission)  # refuse before creating anything
    create_attempt_worktree(spec)
    fakes = None if opts.live else write_fake_bin(task, case_dir / "bin")
    state = opts.state_dir or (default_state_dir() if opts.live else opts.work_dir / "state")
    return Attempt(spec=spec, adapter=adapter, profile=profile, state_dir=state,
                   model=opts.models.get(agent), path_prefix=fakes)


def _profile(opts: ReplayOptions, personal: HarnessProfile, accept: Path) -> HarnessProfile:
    """Replay checks and permissions; budget and host opt-in from the personal profile."""
    host = personal.worker.allow_host_execution or not opts.live
    return HarnessProfile.model_validate({
        "permissions": {"profiles": {**PERMISSIONS, **personal.permissions.model_dump()["profiles"]}},
        "commands": check_commands(accept),
        "validation": {"required": ["test", "e2e"], "check_timeout_s": 120},
        "budget": {"per_run_usd": opts.budget_usd, "per_day_usd": personal.budget.per_day_usd},
        "worker": {"allow_host_execution": host}})


def _spec(opts: ReplayOptions, task: ReplayTask, where: tuple[str, Path]) -> WorkerSpec:
    agent, repo = where
    ref = f"replay-{task.id}-{agent}"
    return WorkerSpec(awg_ref=ref, attempt_id=f"{ref}-{uuid.uuid4().hex[:8]}", fencing_token="replay", stage="build",
                      repo=repo, base_commit=run_git(repo, ["rev-parse", "HEAD"]),
                      spec_version=0, workspace=opts.work_dir / f"{task.id}-{agent}" / "wt",
                      permission="workspace", deadline_s=opts.deadline_s,
                      budget_usd=opts.budget_usd, prompt=replay_prompt(task))
