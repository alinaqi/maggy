"""One worker attempt end to end: launch, runner commit, checks, protected paths (RFC §2.3)."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.harness.schema_sections import Budget
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.budgeted import cost_limit_usd, reservation_usd, run_budgeted
from maggy.worker.checks import CheckPlan, required_commands, run_checks
from maggy.worker.commit import Candidate, commit_candidate
from maggy.worker.env import build_worker_env, with_path_prefix
from maggy.worker.job import Job, Supervised
from maggy.worker.launch import refuse_host_checks, resolve_launch
from maggy.worker.ledger import BudgetLedger
from maggy.worker.models import CheckResult, WorkerResult, WorkerSpec
from maggy.worker.outcome import build_result
from maggy.worker.templating import ArgvValues, render_cwd


@dataclass(frozen=True)
class Attempt:
    """A prepared attempt: the worktree at spec.workspace already exists."""

    spec: WorkerSpec
    adapter: AdapterSpec
    profile: HarnessProfile
    state_dir: Path
    model: str | None = None
    path_prefix: Path | None = None  # dir searched first for the CLI (replay fakes)

    @property
    def attempt_dir(self) -> Path:
        return self.state_dir / "attempts" / self.spec.attempt_id

    @property
    def stop_file(self) -> Path:
        return self.state_dir / "STOP"


def run_attempt(attempt: Attempt) -> WorkerResult:
    """Launch (Refused/BudgetRefused propagate), then commit, check and flag protected paths.

    STOP is re-checked before the commit and before the checks (RFC §2.6.8): once it is
    pulled, nothing more runs and the attempt is reported as failed.
    """
    _refuse_unbounded_checks(attempt)
    run = run_budgeted(_job(attempt), _ledger(attempt), _reservation(attempt))
    stopped = attempt.stop_file.exists
    candidate = Candidate(None) if stopped() else commit_candidate(attempt.spec)
    checks = [] if stopped() else _checks(attempt, candidate)
    if stopped():
        run = replace(run, outcome="failed", reason="stopped")
    return build_result(attempt, run, (candidate, checks))


def _refuse_unbounded_checks(attempt: Attempt) -> None:
    """A run that can write gets checks; refuse before launch if they would lack a boundary."""
    names = [name for name, _ in required_commands(attempt.profile)]
    if names and attempt.adapter.grant(attempt.spec.permission).write:
        refuse_host_checks(attempt.profile, ", ".join(names))


def _budget(attempt: Attempt) -> Budget:
    per_run = attempt.spec.budget_usd or attempt.profile.budget.per_run_usd
    return attempt.profile.budget.model_copy(update={"per_run_usd": per_run})


def _reservation(attempt: Attempt) -> float:
    return reservation_usd(attempt.adapter, _budget(attempt))


def _ledger(attempt: Attempt) -> BudgetLedger:
    return BudgetLedger(attempt.state_dir / "budget.db", attempt.profile.budget.per_day_usd)


def _job(attempt: Attempt) -> Job:
    spec, adapter = attempt.spec, attempt.adapter
    plan = resolve_launch(adapter, attempt.profile, spec.permission)
    workspace = str(spec.workspace)
    values = ArgvValues(spec.prompt, workspace, spec.permission, attempt.model,
                        _budget(attempt).per_run_usd)
    argv = plan.argv(values)
    return Job(run_id=spec.attempt_id, argv=argv, cwd=Path(render_cwd(adapter, workspace)),
               env={**with_path_prefix(build_worker_env(adapter, os.environ), attempt.path_prefix),
                    **plan.env},
               attempt_dir=attempt.attempt_dir, deadline_s=spec.deadline_s,
               parser=adapter.output, cost_limit_usd=cost_limit_usd(adapter, _budget(attempt)),
               stop_file=attempt.stop_file)


def _checks(attempt: Attempt, candidate: Candidate) -> list[CheckResult]:
    if candidate.commit is None:
        return []
    plan = CheckPlan(repo=attempt.spec.repo, sha=candidate.commit,
                     work_dir=attempt.attempt_dir / "checks",
                     commands=required_commands(attempt.profile),
                     timeout_s=attempt.profile.validation.check_timeout_s,
                     profile=attempt.profile)
    return run_checks(plan)
