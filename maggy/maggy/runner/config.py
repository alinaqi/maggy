"""What one runner process works with: repo, state dir, adapter, profile, project."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.awg_types import Claim
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.models import WorkerResult

PrStep = Callable[[Claim, WorkerResult], object]
CAPABILITIES = ["maggy-runner", "stage:build"]  # later stages arrive in Phase 4


@dataclass(frozen=True)
class RunnerConfig:
    repo: Path
    state_dir: Path
    adapter: AdapterSpec
    profile: HarnessProfile
    project: str = "default"
    heartbeat_s: float | None = None  # None: a third of the remaining lease
    pr_step: PrStep | None = None  # runner.publish.Publisher in `maggy run`; fenced per action
