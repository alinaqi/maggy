"""Assemble a local (non-AWG) attempt for `maggy worker run`: dummy AWG fields."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.loader import resolve_profile
from maggy.harness.schema import HarnessProfile
from maggy.worker.adapter_loader import load_adapter
from maggy.worker.git_ops import run_git
from maggy.worker.launch import resolve_launch
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt
from maggy.worker.worktree import create_attempt_worktree


@dataclass(frozen=True)
class RunOptions:
    adapter: str
    repo: Path
    prompt: str
    permission: str | None = None
    deadline_s: int | None = None
    budget_usd: float | None = None


def default_state_dir() -> Path:
    return Path.home() / ".maggy"


def local_attempt(opts: RunOptions, state_dir: Path | None = None) -> Attempt:
    """Resolve profile and adapter, create the attempt worktree and return the Attempt."""
    state = state_dir or default_state_dir()
    repo = Path(run_git(opts.repo, ["rev-parse", "--show-toplevel"]))
    profile = resolve_profile(repo).profile
    adapter = load_adapter(opts.adapter)
    spec = _spec(opts, profile, (repo, state))
    resolve_launch(adapter, profile, spec.permission)  # refuse before creating anything
    create_attempt_worktree(spec)
    return Attempt(spec=spec, adapter=adapter, profile=profile, state_dir=state)


def _spec(opts: RunOptions, profile: HarnessProfile, paths: tuple[Path, Path]) -> WorkerSpec:
    (repo, state), worker = paths, profile.worker
    ref, attempt_id = f"local-{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    budget = opts.budget_usd if opts.budget_usd is not None else profile.budget.per_run_usd
    return WorkerSpec(awg_ref=ref, attempt_id=attempt_id, fencing_token="local", stage="build",
                      repo=repo, base_commit=run_git(repo, ["rev-parse", "HEAD"]),
                      spec_version=0, workspace=state / "worktrees" / ref,
                      permission=opts.permission or worker.permission,
                      deadline_s=opts.deadline_s or worker.timeout_minutes * 60,
                      budget_usd=budget or 0.0, prompt=opts.prompt)
