"""Process supervisor: deadline, kill switch and streaming-cost cap (RFC §2.6.3/4/8)."""

from __future__ import annotations

import subprocess
import time

from maggy.worker.job import Job, Supervised
from maggy.worker.models import Outcome
from maggy.worker.parsers import PARSERS
from maggy.worker.process_group import kill_group, launch

__all__ = ["Job", "Supervised", "supervise"]
Verdict = tuple[Outcome, str]


def supervise(job: Job) -> Supervised:
    """Run the job to completion or until a deadline, STOP file or cost cap kills it."""
    if job.halted():
        return _result(job, ("failed", "stopped"), None)
    started = time.monotonic()
    proc = launch(job)
    try:
        verdict = _watch_and_reap(job, proc, started)
    finally:
        if job.pid_file is not None:
            job.pid_file.unlink(missing_ok=True)
    code = proc.returncode
    verdict = verdict or (("succeeded", "exit code 0") if code == 0
                          else ("failed", f"exit code {code}"))
    return _result(job, verdict, (proc, time.monotonic() - started))


def _watch_and_reap(job: Job, proc: subprocess.Popen, started: float) -> Verdict | None:
    try:
        verdict = _watch(job, proc, started)
    except BaseException:
        kill_group(proc, 0.0)
        raise
    kill_group(proc, 0.0 if verdict is None else job.grace_s)
    return verdict


def _watch(job: Job, proc: subprocess.Popen, started: float) -> Verdict | None:
    """Poll until the process exits (None) or a limit trips (its verdict)."""
    while proc.poll() is None:
        verdict = _limit_tripped(job, time.monotonic() - started)
        if verdict:
            return verdict
        time.sleep(job.poll_s)
    return None


def _limit_tripped(job: Job, elapsed_s: float) -> Verdict | None:
    if elapsed_s >= job.deadline_s:
        return "timeout", "deadline"
    if job.halted():
        return "failed", "stopped"
    limit = job.cost_limit_usd
    if limit is not None and (_cost(job) or 0.0) > limit:
        return "budget_exceeded", "budget"
    return None


def _cost(job: Job) -> float | None:
    """Cost so far, parsed from the stdout log (tolerant of a truncated stream)."""
    text = job.stdout_log.read_text(errors="replace") if job.stdout_log.exists() else ""
    return PARSERS[job.parser](text).cost_usd


def _result(job: Job, verdict: Verdict, ran: tuple[subprocess.Popen, float] | None) -> Supervised:
    proc, elapsed = ran if ran else (None, 0.0)
    return Supervised(outcome=verdict[0], reason=verdict[1], launched=proc is not None,
                      exit_code=proc.returncode if proc else None, elapsed_s=elapsed,
                      cost_usd=_cost(job) if proc else None,
                      stdout_log=job.stdout_log, stderr_log=job.stderr_log)
