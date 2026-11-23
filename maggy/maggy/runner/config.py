"""What one runner process works with: repo, state dir, adapter, profile, project."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.awg_types import Claim
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.models import WorkerResult

PrStep = Callable[[Claim, WorkerResult], object]
CAPABILITIES = ["maggy-runner", "stage:build"]
STAGES = ["stage:spec", "stage:plan"]  # stages held beyond build
REQUIRED = ["maggy-runner"]  # opt-in: untagged items are never claimed (RFC §2.4)  # later stages arrive in Phase 4


def project_capability(project: str) -> str:
    """The capability binding an item to one project (a runner is bound per repo, RFC §2.4)."""
    return f"project:{project}"


def claim_capabilities(project: str) -> tuple[list[str], list[str]]:
    """(held, required) for a runner bound to `project`: it only claims that project's items."""
    tag = project_capability(project)
    return [*CAPABILITIES, *STAGES, tag], [*REQUIRED, tag]


@dataclass(frozen=True)
class RunnerConfig:
    repo: Path
    state_dir: Path
    adapter: AdapterSpec
    profile: HarnessProfile
    project: str = "default"
    heartbeat_s: float | None = None  # None: a third of the remaining lease
    pr_step: PrStep | None = None  # runner.publish.Publisher in `maggy run`; fenced per action
    state_file: Path | None = None  # held leases; None: <state_dir>/runner/state.json
    max_failures: int = 3  # consecutive failed attempts before the item waits for a human
    adapters: dict[str, AdapterSpec] = field(default_factory=dict)  # by name, for stage roles
