"""Worker spec and result models (RFC personal-harness §2.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from maggy.harness.schema_sections import Strict

Stage = Literal["spec", "plan", "build", "verify", "pr", "deploy"]
Outcome = Literal["succeeded", "failed", "blocked", "timeout", "budget_exceeded"]


class Blocker(Strict):
    question: str = Field(min_length=1)
    options: list[str] = []


class CheckResult(Strict):
    """One repo command run by the runner on the candidate commit."""

    name: str
    command: str
    exit_code: int | None
    passed: bool
    sha: str
    duration_s: float = Field(ge=0)
    log_path: Path | None = None

    @model_validator(mode="after")
    def _passed_needs_zero_exit(self) -> CheckResult:
        if self.passed and self.exit_code != 0:
            raise ValueError("exit_code must be 0 when passed is true")
        return self


class WorkerSpec(Strict):
    """Everything one worker attempt needs; AWG fields are plain data here."""

    awg_ref: str
    attempt_id: str
    fencing_token: str
    stage: Stage
    repo: Path
    base_commit: str
    spec_version: int = Field(ge=0)
    workspace: Path
    permission: str
    deadline_s: int = Field(gt=0)
    budget_usd: float = Field(ge=0)
    prompt: str


class WorkerResult(Strict):
    outcome: Outcome
    candidate_commit: str | None = None
    changed_files: list[str] = []
    checks: list[CheckResult] = []
    artifacts: list[str] = []
    blocker: Blocker | None = None
    cost_usd: float = Field(0.0, ge=0)
    elapsed_s: float = Field(ge=0)
    agent: str
    model: str
    adapter_version: str

    @model_validator(mode="after")
    def _blocked_needs_blocker(self) -> WorkerResult:
        if self.outcome == "blocked" and self.blocker is None:
            raise ValueError("outcome 'blocked' requires a blocker")
        return self
