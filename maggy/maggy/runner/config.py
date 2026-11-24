"""What one runner process works with: repo, state dir, adapter, profile, project."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.pr_evidence.council import ReviewCouncil
from maggy.worker.adapter_spec import AdapterSpec

PrStep = Callable[..., object]  # (claim, result[, evidence markdown])
RUNNER = "maggy-runner"
STAGES = ("spec", "plan", "build", "verify")  # every stage the runner can drive, in flow order
CAPABILITIES = [RUNNER, "stage:spec"]  # what intake tags new items with: they start at spec
REQUIRED = [RUNNER]  # opt-in: untagged items are never claimed (RFC §2.4)


def project_capability(project: str) -> str:
    """The capability binding an item to one project (a runner is bound per repo, RFC §2.4)."""
    return f"project:{project}"


def claim_capabilities(project: str, stages: list[str] | tuple[str, ...] = STAGES
                       ) -> tuple[list[str], list[str]]:
    """(held, required) for a runner bound to `project`: it only claims that project's items,
    and only those whose `stage:<name>` is one of `stages` (`worker.stages` in the profile)."""
    tag = project_capability(project)
    held = [f"stage:{stage}" for stage in STAGES if stage in stages]
    return [RUNNER, *held, tag], [*REQUIRED, tag]


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
    vision: list | None = None  # verify-stage vision backends; None: local Ollama Qwen-VL
    council: ReviewCouncil | None = None  # verify-stage PR review; None: a recorded gap
    uploader: Callable[[Path], str] | None = None  # screenshot uploads (publish_screenshots)
