"""The harness profile: personal and repo sections in one strict model."""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator

from maggy.harness.schema_sections import (
    Agents, Budget, Commands, Gates, Hooks, Instructions, Intake, Models,
    Permissions, Risk, Strict, Validation, Work, Worker,
)


class HarnessProfile(Strict):
    """Resolved or per-file harness profile. Every key has a shipped default."""

    version: Literal[1] = 1
    agents: Agents = Agents()
    surfaces: list[str] = []
    models: Models = Models()
    instructions: Instructions = Instructions()
    skills: list[str] = []
    hooks: Hooks = Hooks()
    permissions: Permissions = Permissions()
    gates: Gates = Gates()
    work: Work = Work()
    budget: Budget = Budget()
    commands: Commands = Commands()
    intake: Intake = Intake()
    worker: Worker = Worker()
    risk: Risk = Risk()
    validation: Validation = Validation()
    locked: list[str] = []

    @field_validator("locked")
    @classmethod
    def _locked_names_profile_keys(cls, value: list[str]) -> list[str]:
        unknown = [key for key in value if key.split(".")[0] not in cls.model_fields]
        if unknown:
            raise ValueError(f"unknown profile key(s) in locked: {', '.join(unknown)}")
        return value


def shipped_defaults() -> dict:
    """The lowest layer: every key at its built-in default."""
    return HarnessProfile().model_dump()
