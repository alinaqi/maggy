"""harness.lock: what Maggy last wrote into each managed region.

Per file (keyed by resolved path) and region id it keeps the sha256 of the
region text plus the text itself, so a conflict can show a 3-way diff. An
entry also records its format, scope root and owning agents (so a region the
profile drops can be found and removed), and `base`: the profile text at the
time the user kept their own version with --take-mine (None otherwise).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from maggy.harness.fs_safe import atomic_write, real


def region_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LockEntry(BaseModel):
    sha256: str
    content: str | None
    base: str | None = None
    format: str | None = None
    agents: list[str] = Field(default_factory=list)
    root: str | None = None

    def matches(self, disk: str | None) -> bool:
        """True when the on-disk region text is what Maggy last wrote (None: absent)."""
        if self.content is None:
            return disk is None
        return disk is not None and region_hash(disk) == self.sha256


def entry_for(content: str | None, **meta: object) -> LockEntry:
    return LockEntry(sha256=region_hash(content or ""), content=content, **meta)


class HarnessLock(BaseModel):
    version: int = 1
    files: dict[str, dict[str, LockEntry]] = Field(default_factory=dict)

    def get(self, path: Path, rid: str) -> LockEntry | None:
        return self.entries(path).get(rid)

    def entries(self, path: Path) -> dict[str, LockEntry]:
        return dict(self.files.get(str(real(path)), {}))

    def record(self, path: Path, texts: dict[str, str]) -> None:
        self.set_file(path, {rid: entry_for(t) for rid, t in texts.items()})

    def set_file(self, path: Path, entries: dict[str, LockEntry]) -> None:
        if entries:
            self.files[str(real(path))] = dict(entries)
        else:
            self.forget(path)

    def forget(self, path: Path) -> None:
        self.files.pop(str(real(path)), None)


def load_lock(path: Path) -> HarnessLock:
    if not path.exists():
        return HarnessLock()
    return HarnessLock.model_validate_json(path.read_text(encoding="utf-8"))


def save_lock(lock: HarnessLock, path: Path) -> None:
    atomic_write(path, lock.model_dump_json(indent=2) + "\n", 0o600)
