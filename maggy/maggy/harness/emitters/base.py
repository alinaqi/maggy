"""Emitter protocol and shared models (RFC personal-harness §2.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.schema import HarnessProfile

Level = Literal["native", "partial", "none"]


class Capability(BaseModel):
    level: Level
    notes: str


class Capabilities(BaseModel):
    instructions: Capability
    skills: Capability
    hooks: Capability
    mcp: Capability
    permissions: Capability


class EmitterSources(BaseModel):
    """Where instruction includes and skills are read from."""

    model_config = ConfigDict(extra="forbid")
    root: Path
    awg_repo: Path | None = None


class Scope(BaseModel):
    """user: root is HOME. project: root is the repo; home locates tokens and state."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["user", "project"]
    root: Path
    home: Path

    def context(self) -> HarnessContext:
        state = self.home / ".maggy"
        return HarnessContext(root=self.root, lock_path=state / "harness.lock",
                              backups_dir=state / "backups")


@runtime_checkable
class Emitter(Protocol):
    agent: str

    def capabilities(self) -> Capabilities: ...

    def plan(self, profile: HarnessProfile, scope: Scope) -> list[FileChange]: ...
