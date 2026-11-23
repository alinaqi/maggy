"""One worker attempt end to end: launch, runner commit, checks, protected paths (RFC §2.3)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.harness.schema_sections import Budget
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.blocker import agent_blocker
from maggy.worker.budgeted import cost_limit_usd, reservation_usd, run_budgeted
from maggy.worker.checks import CheckPlan, required_commands, run_checks
from maggy.worker.commit import Candidate, commit_candidate
from maggy.worker.env import build_worker_env, with_path_prefix
from maggy.worker.job import Job, Supervised
from maggy.worker.launch import resolve_launch
from maggy.worker.ledger import BudgetLedger
from maggy.worker.models import CheckResult, WorkerResult, WorkerSpec
from maggy.worker.parsers import RawRun, parse_run
from maggy.worker.protected import protected_blocker, protected_paths
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


def run_attempt(attempt: Attempt) -> WorkerResult:
    """Launch (Refused/BudgetRefused propagate), then commit, check and flag protected paths."""
    run = run_budgeted(_job(attempt), _ledger(attempt), _reservation(attempt))
    candidate = commit_candidate(attempt.spec)
    checks = _checks(attempt, candidate)
    return _result(attempt, run, (candidate, checks))


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
               stop_file=attempt.state_dir / "STOP")


def _checks(attempt: Attempt, candidate: Candidate) -> list[CheckResult]:
    if candidate.commit is None:
        return []
    plan = CheckPlan(repo=attempt.spec.repo, sha=candidate.commit,
                     work_dir=attempt.attempt_dir / "checks",
                     commands=required_commands(attempt.profile),
                     timeout_s=attempt.profile.validation.check_timeout_s)
    return run_checks(plan)


def _result(attempt: Attempt, run: Supervised,
            found: tuple[Candidate, list[CheckResult]]) -> WorkerResult:
    candidate, checks = found
    adapter = attempt.adapter
    parsed = parse_run(adapter.output, _raw(run), adapter.quota_patterns)
    blocker = (protected_blocker(protected_paths(candidate.changed_files, attempt.profile))
               or agent_blocker(parsed.final_text))
    outcome = "blocked" if blocker and run.outcome == "succeeded" else run.outcome
    return WorkerResult(outcome=outcome, candidate_commit=candidate.commit,
                        changed_files=candidate.changed_files, checks=checks,
                        artifacts=[str(run.stdout_log), str(run.stderr_log)], blocker=blocker,
                        cost_usd=run.cost_usd or parsed.cost_usd or 0.0, elapsed_s=run.elapsed_s,
                        agent=adapter.name, model=parsed.model or attempt.model or "unknown",
                        adapter_version=adapter.tested_version or "unknown")


def _raw(run: Supervised) -> RawRun:
    def read(path: Path) -> str:
        return path.read_text(errors="replace") if path.exists() else ""
    return RawRun(stdout=read(run.stdout_log), stderr=read(run.stderr_log),
                  exit_code=run.exit_code)
