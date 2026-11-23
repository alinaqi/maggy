"""Kill switch and intake pause (RFC §2.6.8).

`STOP` in the state dir halts every claim and side effect; `maggy run stop` also kills the
worker process groups registered under `runner/pids/<attempt>.pid` (only while each leader
is still the recorded process: `maggy.worker.pidfile`). A per-project pause flag
stops intake for that project only.
"""

from __future__ import annotations

import re
from pathlib import Path

from maggy.worker.pidfile import kill_recorded

_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def stop_file(state: Path) -> Path:
    return state / "STOP"


def pid_dir(state: Path) -> Path:
    return state / "runner" / "pids"


def pause_flag(state: Path, project: str) -> Path:
    """The pause flag for `project` (a plain name: never a path)."""
    if not _PROJECT.match(project):
        raise ValueError(f"invalid project key {project!r}")
    return state / "runner" / "paused" / project


def is_paused(state: Path, project: str) -> bool:
    return pause_flag(state, project).exists()


def set_paused(state: Path, project: str, paused: bool) -> None:
    flag = pause_flag(state, project)
    if paused:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("paused\n")
    else:
        flag.unlink(missing_ok=True)


def request_stop(state: Path) -> int:
    """Create STOP, then SIGKILL every registered worker group; returns how many were killed."""
    stop_file(state).parent.mkdir(parents=True, exist_ok=True)
    stop_file(state).write_text("stop\n")
    return sum(kill_recorded(path) for path in sorted(pid_dir(state).glob("*.pid")))
