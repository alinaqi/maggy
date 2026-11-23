"""harness.lock: what Maggy last wrote into each managed region.

Per file (keyed by resolved path) and region id it keeps the sha256 of the
region text plus the text itself, so a conflict can show a 3-way diff.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from maggy.harness.fs_safe import atomic_write, real


class LockEntry(BaseModel):
    sha256: str
    content: str


class HarnessLock(BaseModel):
    version: int = 1
    files: dict[str, dict[str, LockEntry]] = Field(default_factory=dict)

    def get(self, path: Path, rid: str) -> LockEntry | None:
        return self.files.get(str(real(path)), {}).get(rid)

    def record(self, path: Path, texts: dict[str, str]) -> None:
        entries = {rid: LockEntry(sha256=region_hash(t), content=t) for rid, t in texts.items()}
        self.files[str(real(path))] = entries


def region_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_lock(path: Path) -> HarnessLock:
    if not path.exists():
        return HarnessLock()
    return HarnessLock.model_validate_json(path.read_text(encoding="utf-8"))


def save_lock(lock: HarnessLock, path: Path) -> None:
    atomic_write(path, lock.model_dump_json(indent=2) + "\n", 0o600)
