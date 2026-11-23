"""Models for the managed-regions engine: what to manage, what would change."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from maggy.harness.lock import LockEntry

Format = Literal["markdown", "text", "json", "toml"]
Resolution = Literal["take_mine", "take_profile"]


def _maggy_dir() -> Path:
    return Path.home() / ".maggy"


class ManagedFile(BaseModel):
    """One target file and the regions Maggy owns in it.

    markdown/text: region id -> block body. json/toml: dotted key path -> value,
    or '<path>[]' -> Maggy's entries of a list shared with the user (region_lists).
    owners: region id -> agents that emitted it (recorded in harness.lock).
    """

    model_config = ConfigDict(extra="forbid")
    path: Path
    format: Format
    regions: dict[str, Any]
    references_token: bool = False
    owners: dict[str, list[str]] = Field(default_factory=dict)


class HarnessContext(BaseModel):
    """Where plan/apply may write, where state lives, how to resolve conflicts.

    agents: the agents in this run; a dropped region is removed only when all
    of its owners are in the run (None: only regions with no recorded owner).
    """

    model_config = ConfigDict(extra="forbid")
    root: Path
    lock_path: Path = Field(default_factory=lambda: _maggy_dir() / "harness.lock")
    backups_dir: Path = Field(default_factory=lambda: _maggy_dir() / "backups")
    resolution: Resolution | None = None
    agents: list[str] | None = None


class FileChange(BaseModel):
    """The planned outcome for one managed file.

    kind delete removes a whole Maggy-owned file (e.g. a managed skill copy).
    status: ok (apply writes it), conflict (user edited a managed region),
    invalid (existing file unparseable), refused (path escapes the root).
    Only ok changes are written; the others are reported and skipped.
    lock_entries: the file's harness.lock entries after apply (None: from region_texts).
    """

    path: Path
    kind: Literal["create", "update", "unchanged", "delete"]
    before: str | None
    after: str | None
    managed_ids: list[str]
    status: Literal["ok", "conflict", "invalid", "refused"] = "ok"
    reason: str | None = None
    conflicts: list[str] = Field(default_factory=list)
    diff3: str | None = None
    region_texts: dict[str, str] = Field(default_factory=dict)
    lock_entries: dict[str, LockEntry] | None = None
    references_token: bool = False
