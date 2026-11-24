"""Run one named test in a FRESH detached worktree and classify it (RFC §2.6.2).

RED: a checkout of base with only the candidate's test files overlaid. GREEN: a checkout of
the candidate. The command is argv-only with the check env (no credentials, throwaway HOME)
and the per-check timeout; the worktree is removed afterwards, the log and report are kept.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.regression.invocation import invocation
from maggy.runner.regression.junit import TestRun, classify
from maggy.runner.regression.overlay import overlay_tests
from maggy.worker.checks import run_logged
from maggy.worker.env import build_check_env
from maggy.worker.worktree import add_detached, remove_worktree


@dataclass(frozen=True)
class ProofPlan:
    repo: Path
    commits: tuple[str, str]  # (base, candidate)
    work_dir: Path
    profile: HarnessProfile


def run_named(plan: ProofPlan, test: str, red: bool) -> TestRun:
    """RED (base + candidate tests) when `red`, else GREEN (candidate)."""
    plan.work_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="red-" if red else "green-", dir=plan.work_dir))
    sha = plan.commits[0] if red else plan.commits[1]
    checkout = add_detached(plan.repo, sha, run_dir / "checkout")
    try:
        if red:
            overlay_tests(plan.repo, plan.commits, checkout)
        return _execute(plan, test, (checkout, run_dir))
    finally:
        remove_worktree(plan.repo, checkout)


def _execute(plan: ProofPlan, test: str, dirs: tuple[Path, Path]) -> TestRun:
    checkout, run_dir = dirs
    config = plan.profile.validation.regression
    junit = checkout / config.junit if config.junit else run_dir / "junit.xml"
    junit.unlink(missing_ok=True)  # a committed report must not stand in for this run
    argv, extra = invocation(config, test, junit)
    with tempfile.TemporaryDirectory(prefix="maggy-check-home-") as home:
        env = {**build_check_env(os.environ, home), **extra}
        sink = (run_dir / "run.log", float(plan.profile.validation.check_timeout_s))
        code = run_logged(argv, (checkout, env), sink)
    return classify(junit, code)
