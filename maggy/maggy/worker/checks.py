"""Required checks, run by the runner in a fresh worktree at the candidate (RFC §2.6.2/7).

Each configured command is split with shlex and run as argv (never a shell), with
`build_check_env` (no credentials, throwaway HOME) and a per-check timeout. Checks run
candidate code and there is no check sandbox yet, so they are refused unless the personal
profile sets `worker.allow_host_execution: true` (fail closed, §2.6.7).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.worker.env import build_check_env
from maggy.worker.launch import refuse_host_checks
from maggy.worker.models import CheckResult
from maggy.worker.worktree import add_detached, remove_worktree

Command = tuple[str, str | None]


@dataclass(frozen=True)
class CheckPlan:
    repo: Path
    sha: str
    work_dir: Path
    commands: list[Command]
    timeout_s: float = 600
    profile: HarnessProfile | None = None  # its worker policy gates host execution


def required_commands(profile: HarnessProfile) -> list[Command]:
    """validation.required names mapped to commands.* (None when not configured)."""
    commands = profile.commands.model_dump()
    return [(name, commands.get(name)) for name in profile.validation.required]


def run_checks(plan: CheckPlan) -> list[CheckResult]:
    """Run every command in a fresh detached worktree at plan.sha, then remove it."""
    if not plan.commands:
        return []
    refuse_host_checks(plan.profile or HarnessProfile(), ", ".join(n for n, _ in plan.commands))
    checkout = add_detached(plan.repo, plan.sha, plan.work_dir / "checkout")
    try:
        with tempfile.TemporaryDirectory(prefix="maggy-check-home-") as home:
            env = build_check_env(os.environ, home)
            return [_run_one(plan, (checkout, env), command) for command in plan.commands]
    finally:
        remove_worktree(plan.repo, checkout)


def _run_one(plan: CheckPlan, where: tuple[Path, dict[str, str]], command: Command) -> CheckResult:
    name, line = command
    log = plan.work_dir / f"{name}.log"
    started = time.monotonic()
    code = run_logged(shlex.split(line), where, (log, plan.timeout_s)) if line else None
    return CheckResult(name=name, command=line or "", exit_code=code, passed=code == 0,
                       sha=plan.sha, duration_s=time.monotonic() - started,
                       log_path=log if line else None)


def run_logged(argv: list[str], where: tuple[Path, dict[str, str]],
          sink: tuple[Path, float]) -> int | None:
    """Exit code, or None when the command is missing or timed out."""
    log, timeout_s = sink
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as out:
        try:
            return subprocess.run(argv, cwd=where[0], env=where[1], stdout=out,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  timeout=timeout_s, check=False).returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            out.write(f"\nmaggy: {exc}\n".encode())
            return None
