"""One runner per state dir (RFC §2.4 crash recovery).

Reconciliation treats every lease in the state file as left by a crash, which is only true
when no other runner is alive on the same state dir. `RunnerLock` is an exclusive, non-
blocking `flock` on `<state_dir>/runner/runner.lock`: the kernel drops it when the holder
dies (including SIGKILL), so a restarted runner gets it and a concurrent one does not.
Re-entrant within one RunnerLock, so `run()` can hold it across `run_once()` passes.
"""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import IO


class Locked(Exception):
    """Another live runner holds this state dir."""


def lock_path(state_dir: Path) -> Path:
    return state_dir / "runner" / "runner.lock"


class RunnerLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: IO[str] | None = None
        self._depth = 0

    @property
    def held(self) -> bool:
        return self._depth > 0

    def __enter__(self) -> RunnerLock:
        if self._depth == 0:
            self._file = self._acquire()
        self._depth += 1
        return self

    def __exit__(self, *exc: object) -> None:
        self._depth -= 1
        if self._depth == 0 and self._file is not None:
            self._file.close()  # closing the descriptor releases the flock
            self._file = None

    def _acquire(self) -> IO[str]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise Locked(f"another maggy run holds {self.path}") from exc
        return handle
