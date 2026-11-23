"""Worker pid registry entries that name one process, not just a pid (RFC §2.6.3, §2.6.8).

`<pid> <start time>`: a pid alone can be reused by any later process (and any shell or
setsid daemon leads its own group), so a group is only killed while its leader still has
the start time recorded at launch. An entry without one is never acted on.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def start_time(pid: int) -> str:
    """The process's start time as `ps` reports it ("" when it is gone or unknown)."""
    try:
        done = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                              text=True, check=False, stdin=subprocess.DEVNULL, timeout=10,
                              env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return " ".join(done.stdout.split()) if done.returncode == 0 else ""


def write_pid_file(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{pid} {start_time(pid)}\n")


def recorded_leader(path: Path) -> int | None:
    """The recorded pid while it still is the same process and leads its group."""
    try:
        pid_text, _, started = path.read_text().strip().partition(" ")
        pid = int(pid_text)
        if pid <= 1 or not started or os.getpgid(pid) != pid:
            return None
    except (ValueError, OSError):
        return None
    return pid if start_time(pid) == " ".join(started.split()) else None


def kill_recorded(path: Path) -> bool:
    """SIGKILL the recorded worker group if it is still that worker; True when killed."""
    pid = recorded_leader(path)
    if pid is None:
        return False
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        return False
    return True
