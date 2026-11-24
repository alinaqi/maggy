"""A visual criterion checked by the repo's OWN Playwright config (factory doc §5 "Run it as
a gate"): its named test runs like a regression GREEN run (fresh worktree at the candidate,
check env, junit) with `--update-snapshots=none`, so a missing snapshot is reported, never
written. A missing snapshot is PENDING (generate one with `--update-snapshots=missing` and
approve it); any other failure is FAIL; a repo without Playwright and no Maggy visual spec
is PENDING (no visual check described).
"""

from __future__ import annotations

import shlex

from maggy.harness.schema import HarnessProfile
from maggy.runner.regression.invocation import DEFAULTS
from maggy.runner.regression.run import ProofPlan, run_named
from maggy.runner.verify.models import ViewResult, VisualJob
from maggy.worker.launch import refuse_host_checks

VIEWPORT = "repo-playwright"
GATE_FLAG = "--update-snapshots=none"
MISSING = ("snapshot doesn't exist", "snapshot does not exist", "missing snapshot")


def run_repo_visual(job: VisualJob, entry: dict) -> ViewResult:
    criterion, test = str(entry["criterion_id"]), str(entry["regression_test_name"])
    regression = job.profile.validation.regression
    if regression.runner != "playwright":
        return ViewResult(criterion, VIEWPORT, "PENDING",
                          "no visual check described (no visual spec, no repo Playwright)",
                          blocked=True)
    refuse_host_checks(job.profile, f"visual check {test}")
    work = job.work_dir / "visual" / criterion
    run = run_named(ProofPlan(job.repo, (job.sha, job.sha), work, _gated(job.profile)), test,
                    red=False)
    logs = sorted(work.glob("green-*/run.log"))
    artifacts = {"log": logs[-1]} if logs else {}
    if run.kind == "passed":
        return ViewResult(criterion, VIEWPORT, "PASS", "repo Playwright test passed", artifacts)
    if any(marker in run.trace.lower() for marker in MISSING):
        return ViewResult(criterion, VIEWPORT, "PENDING",
                          "no approved snapshot: run with --update-snapshots=missing and "
                          "approve it", artifacts)
    return ViewResult(criterion, VIEWPORT, "FAIL", f"{run.kind}: {run.trace}"[:1500], artifacts)


def _gated(profile: HarnessProfile) -> HarnessProfile:
    """`profile` with the repo's Playwright command run with `--update-snapshots=none`."""
    regression = profile.validation.regression
    command = f"{regression.command or DEFAULTS['playwright']} {shlex.quote(GATE_FLAG)}"
    gated = regression.model_copy(update={"command": command})
    validation = profile.validation.model_copy(update={"regression": gated})
    return profile.model_copy(update={"validation": validation})
