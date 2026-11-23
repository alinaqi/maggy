"""Startup reconciliation after a crash (RFC §2.4 crash recovery, §2.6.3).

Only one runner owns a state dir (`runner.lock`), so every lease in it was left by a dead
run. For each: kill that run's orphaned worker group (it outlives the runner), settle dangling publish intents from
external state, then roll forward when the lease is still ours and the worker had finished
(re-run conclude: evidence is attached once, push and PR are idempotent by stable name, then
submit), else roll back (release with a handoff: what was done, last SHA, next step). The
worktree and branch are always kept, so the re-claim resumes from the branch.
"""

from __future__ import annotations

from maggy.runner.attempt import workspace_for
from maggy.runner.awg_types import Claim
from maggy.runner.control import pid_dir
from maggy.runner.awg_client import AwgClient
from maggy.runner.awg_errors import LeaseLost
from maggy.runner.conclude import conclude
from maggy.runner.config import RunnerConfig
from maggy.runner.drive import guarded
from maggy.runner.publish_git import branch_for
from maggy.runner.session import RunReport, Session
from maggy.runner.state import state_for
from maggy.runner.workspace import safe_name
from maggy.worker.git_ops import GitError, run_git
from maggy.worker.models import WorkerResult
from maggy.worker.pidfile import kill_recorded


def reconcile(awg: AwgClient, config: RunnerConfig) -> list[RunReport]:
    """Resolve every held lease left by a previous (crashed) run; one report each."""
    state = state_for(config)
    reports = []
    for claim, result in state.held():
        session = Session(awg, claim, config)
        session.log("reconcile", {"worker_finished": result is not None,
                                  "orphan_killed": reap_orphan(config, claim)})
        reports.append(guarded(session, lambda s=session, r=result: _resolve(s, r)))
        state.drop(claim.ref)
    return reports


def reap_orphan(config: RunnerConfig, claim: Claim) -> bool:
    """Kill the dead runner's worker group for `claim` (it survives the runner: own session)
    and drop its pid entry, before the item is released or rolled forward (§2.6.3)."""
    pid_file = pid_dir(config.state_dir) / f"{safe_name(claim.attempt_id)}.pid"
    killed = kill_recorded(pid_file)
    pid_file.unlink(missing_ok=True)
    return killed


def _resolve(session: Session, result: WorkerResult | None) -> RunReport:
    session.settle_intents()
    if result is not None and _still_held(session):
        session.log("roll_forward", {"sha": result.candidate_commit})
        return conclude(session, result)
    return session.give_back("interrupted", handoff_text(session, result))


def _still_held(session: Session) -> bool:
    try:
        session.verify()
    except LeaseLost:
        return False
    return True


def handoff_text(session: Session, result: WorkerResult | None) -> str:
    """What was done, the branch's last SHA and the next step, for the next attempt."""
    branch = branch_for(session.claim.ref)
    sha = _branch_head(session, branch)
    done = ("the worker finished and its checks ran, but publishing did not complete"
            if result is not None else "the worker did not finish (nothing was checked)")
    return (f"runner crashed: {done}. Last SHA {sha or 'none'} on {branch}; worktree kept "
            f"at {workspace_for(session)}. Next step: the re-claim resumes from {branch}, "
            "re-runs the required checks on its head, then pushes, updates the draft PR "
            "and submits.")


def _branch_head(session: Session, branch: str) -> str:
    try:
        return run_git(session.config.repo, ["rev-parse", "--verify", "-q",
                                             f"refs/heads/{branch}"])
    except GitError:
        return ""
