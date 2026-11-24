"""Section models of the harness profile (RFC personal-harness, section 2.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    """Base for every profile section: unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")


class Agents(Strict):
    installed: list[str] = []
    default: str | None = None
    prefer: dict[str, str] = {}


class Models(Strict):
    strategy: Literal["cost", "quality", "speed", "custom"] = "cost"
    tiers: dict[str, str] = {}


class Instructions(Strict):
    include: list[str] = []


class Hooks(Strict):
    """Abstract lifecycle events, mapped to native hooks per agent."""

    session_start: list[str] = []
    before_tool: list[str] = []
    after_tool: list[str] = []
    after_edit: list[str] = []
    before_stop: list[str] = []
    before_compact: list[str] = []
    session_end: list[str] = []


class PermissionProfile(Strict):
    write: bool | Literal["workspace"] = False
    network: bool | Literal["registries"] = False
    shell: bool | Literal["allowlist"] = False


class Permissions(Strict):
    profiles: dict[str, PermissionProfile] = {}


class QualityGates(Strict):
    max_function_lines: int = Field(20, gt=0)
    max_params: int = Field(3, gt=0)
    max_nesting: int = Field(2, gt=0)
    max_file_lines: int = Field(200, gt=0)
    max_functions_per_file: int = Field(10, gt=0)


class Gates(Strict):
    tdd: Literal["required", "preferred", "off"] = "required"
    coverage_min: float = Field(0.8, ge=0, le=1)
    quality: QualityGates = QualityGates()


class Work(Strict):
    provider: Literal["awg", "none"] = "awg"
    project: str = "auto"


class Budget(Strict):
    per_run_usd: float | None = Field(None, ge=0)
    per_day_usd: float | None = Field(None, ge=0)


class Commands(Strict):
    install: str | None = None
    build: str | None = None
    test: str | None = None
    lint: str | None = None
    typecheck: str | None = None
    format: str | None = None
    e2e: str | None = None


class Intake(Strict):
    source: Literal["github", "awg", "none"] = "none"
    label: str | None = None
    status: str = "open"
    capabilities: list[str] | None = None  # None: maggy-runner, stage:spec (start at spec)


class Worker(Strict):
    adapter: str | None = None
    permission: str = "workspace"
    timeout_minutes: int = Field(30, gt=0)
    isolation: Literal["worktree", "container"] = "worktree"
    allow_host_execution: bool = False  # personal profile only (loader enforces)
    stages: list[Literal["spec", "plan", "build"]] = ["spec", "plan", "build"]  # claimable


class RiskRule(Strict):
    paths: list[str] = []
    require: Literal["plan_approval", "human_review"] | None = None
    autonomy: Literal["none", "draft_pr", "pr", "merge"] | None = None


class Risk(Strict):
    high: RiskRule | None = None
    medium: RiskRule | None = None
    low: RiskRule | None = None


class Regression(Strict):
    """How the runner runs ONE named regression test with a junit report (RED/GREEN proof).

    `command` overrides the runner's base argv (pytest: `python -m pytest`); for
    `runner: command` it is required and may use `{test}` / `{junit}` placeholders, and
    `junit` names the report path relative to the checkout when the tool picks its own.
    """

    runner: Literal["pytest", "node-test", "playwright", "command"] = "pytest"
    command: str | None = None
    junit: str | None = None

    @model_validator(mode="after")
    def _command_runner_needs_command(self) -> Regression:
        if self.runner == "command" and not self.command:
            raise ValueError("regression.runner 'command' requires regression.command")
        return self


class Validation(Strict):
    required: list[str] = []
    visual_for: list[str] = []
    check_timeout_s: int = Field(600, gt=0)  # per required check run by the runner
    regression: Regression = Regression()
