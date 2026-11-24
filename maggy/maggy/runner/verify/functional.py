"""Functional verification on the integrated candidate (RFC §2.5 Verify, §2.6.2).

Repo commands (`validation.required`) and each criterion's planned functional test
(unit/integration/e2e evidence) run in fresh detached worktrees at the candidate with the
check env (no credentials, throwaway HOME), reusing the worker checks and the regression
GREEN run.
"""

from __future__ import annotations

from maggy.runner.regression.run import ProofPlan, run_named
from maggy.runner.verify.models import ViewResult, VisualJob
from maggy.worker.launch import refuse_host_checks
from maggy.worker.checks import CheckPlan, required_commands, run_checks
from maggy.worker.models import CheckResult

FUNCTIONAL = ("unit", "integration", "e2e")
CHECK = "functional"


def run_repo_commands(job: VisualJob) -> list[CheckResult]:
    profile = job.profile
    plan = CheckPlan(repo=job.repo, sha=job.sha, work_dir=job.work_dir / "commands",
                     commands=required_commands(profile),
                     timeout_s=float(profile.validation.check_timeout_s), profile=profile)
    return run_checks(plan)


def run_functional(job: VisualJob, entry: dict) -> ViewResult:
    """The criterion's named test on the candidate: PASS only when it really ran and passed."""
    criterion, test = str(entry["criterion_id"]), str(entry["regression_test_name"])
    refuse_host_checks(job.profile, f"functional check {test}")
    work = job.work_dir / CHECK / criterion
    run = run_named(ProofPlan(job.repo, (job.sha, job.sha), work, job.profile), test, red=False)
    logs = sorted(work.glob("green-*/run.log"))
    artifacts = {"log": logs[-1]} if logs else {}
    if run.kind == "passed":
        return ViewResult(criterion, "", "PASS", f"{test} passed", artifacts, CHECK)
    return ViewResult(criterion, "", "FAIL", f"{test}: {run.kind}: {run.trace}"[:1500],
                      artifacts, CHECK)
