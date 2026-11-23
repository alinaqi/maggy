"""Launch and kill a worker as its own process group (RFC §2.6.3, §2.6.4).

The worker is the leader of a new session, so signalling its group reaches every
child and grandchild it spawned (unless one deliberately starts its own session).
"""

from __future__ import annotations

import os
import signal
import subprocess

from maggy.worker.job import Job


class LaunchFailed(OSError):
    """The worker process could not be started (nothing ran, nothing was spent)."""


def launch(job: Job) -> subprocess.Popen:
    """Start the job's argv (never via a shell) in a new session, logging to files."""
    job.attempt_dir.mkdir(parents=True, exist_ok=True)
    with job.stdout_log.open("wb") as out, job.stderr_log.open("wb") as err:
        try:
            proc = subprocess.Popen(job.argv, cwd=job.cwd, env=job.env, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise LaunchFailed(f"could not start {job.argv[0]!r}: {exc}") from exc
    if job.pid_file is not None:  # the leader's pid is its group id (new session)
        job.pid_file.parent.mkdir(parents=True, exist_ok=True)
        job.pid_file.write_text(f"{proc.pid}\n")
    return proc


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def kill_group(proc: subprocess.Popen, grace_s: float) -> None:
    """SIGTERM the whole group, SIGKILL it after `grace_s`, then reap the leader."""
    _signal_group(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        pass
    _signal_group(proc.pid, signal.SIGKILL)
    proc.wait()
