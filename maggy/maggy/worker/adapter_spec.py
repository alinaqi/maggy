"""Schema of a data-driven worker adapter (`worker/adapters/*.yaml`)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from maggy.harness.schema_sections import Strict
from maggy.worker.env_rules import auth_file_problem, provider_key_problem
from maggy.worker.templating import SPLATS, WHOLE, placeholder_problem

Parser = Literal["claude-json", "codex-jsonl", "opencode-json", "pi-jsonl", "text"]


def _elements(allowed: frozenset[str]):
    def check(value: list[str]) -> list[str]:
        problems = [f"element {i}: {problem}" for i, item in enumerate(value)
                    if (problem := placeholder_problem(item, allowed))]
        if problems:
            raise ValueError("; ".join(problems))
        return value
    return AfterValidator(check)


def _one_prompt(value: list[str]) -> list[str]:
    if value.count("{prompt}") != 1:
        raise ValueError("argv must contain '{prompt}' exactly once")
    return value


def _cwd(value: str) -> str:
    problem = placeholder_problem(value, frozenset({"{workspace}"}))
    if problem:
        raise ValueError(problem)
    return value


Literals = Annotated[list[str], _elements(frozenset())]
Template = Annotated[list[str], Field(min_length=1), _elements(WHOLE | SPLATS),
                     AfterValidator(_one_prompt)]
ModelFlags = Annotated[list[str], _elements(frozenset({"{model}"}))]
BudgetFlags = Annotated[list[str], _elements(frozenset({"{budget_usd}"}))]
Cwd = Annotated[str, AfterValidator(_cwd)]


class Sandbox(Strict):
    native: bool = False
    notes: str = ""


def _each(rule):
    def check(value: list[str]) -> list[str]:
        problems = [problem for item in value if (problem := rule(item))]
        if problems:
            raise ValueError("; ".join(problems))
        return value
    return AfterValidator(check)


class AdapterEnv(Strict):
    provider_keys: Annotated[list[str], _each(provider_key_problem)] = []
    auth_files: Annotated[list[str], _each(auth_file_problem)] = []


class DisableAwg(Strict):
    flags: Literals = []
    env: dict[str, str] = {}


class Cost(Strict):
    streams: bool = False
    fixed_reservation_usd: float | None = Field(None, ge=0)


class AdapterSpec(Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version_range: str | None = None
    tested_version: str | None = None
    detect: Annotated[Literals, Field(min_length=1)]
    argv: Template
    cwd: Cwd = "{workspace}"
    model_flags: ModelFlags = []
    budget_flags: BudgetFlags = []  # rendered with per_run_usd; dropped when unset
    permissions: dict[str, Literals] = {}
    permission_env: dict[str, dict[str, str]] = {}
    sandbox: Sandbox = Sandbox()
    output: Parser
    instruction_file: str | None = None
    quota_patterns: list[str] = []
    env: AdapterEnv = AdapterEnv()
    disable_awg: DisableAwg = DisableAwg()
    cost: Cost = Cost()

    @model_validator(mode="after")
    def _permission_env_is_safe(self) -> AdapterSpec:
        unknown = sorted(set(self.permission_env) - set(self.permissions))
        if unknown:
            raise ValueError(f"permission_env names unknown profile(s): {', '.join(unknown)}")
        clash = sorted({key for env in self.permission_env.values() for key in env}
                       & set(self.disable_awg.env))
        if clash:
            raise ValueError(f"permission_env must not override disable_awg.env: {', '.join(clash)}")
        return self
