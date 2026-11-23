"""Drive one claimed item: stage gate, worktree, worker under heartbeat, then conclude.

Lease loss (heartbeat failure or a stale fence anywhere) means stopping, not finishing:
the worker's group is killed, no evidence/PR/submit happens, the worktree is kept and the
attempt is given back as interrupted (RFC §2.6.3).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from maggy.runner.attempt import build_attempt, item_stage, workspace_for
from maggy.runner.awg_errors import LeaseLost
from maggy.runner.conclude import conclude
from maggy.runner.heartbeat import Heartbeat
from maggy.runner.session import RunReport, Session, Stopped
from maggy.runner.state import latest_handoff, state_for
from maggy.runner.workspace import prepare_workspace
from maggy.worker.models import WorkerResult
from maggy.worker.pipeline import run_attempt


class Interrupted(LeaseLost):
    """The heartbeat thread lost the lease while the worker ran."""


def drive(session: Session) -> RunReport:
    return guarded(session, lambda: _drive(session))


def guarded(session: Session, step: Callable[[], RunReport]) -> RunReport:
    """Run `step`; lease loss, STOP or any failure gives the item back with a handoff."""
    try:
        return step()
    except LeaseLost as exc:
        workspace = workspace_for(session)
        return session.give_back("interrupted", f"{exc}; worktree kept at {workspace}")
    except Stopped as exc:
        return session.give_back("stopped", str(exc))
    except Exception as exc:  # the loop must survive one bad item; the reason is logged
        return session.give_back("failed", f"{type(exc).__name__}: {exc}"[:500])


def _drive(session: Session) -> RunReport:
    shown = session.awg.show(session.claim.ref)
    stage = item_stage(shown)
    if stage != "build":
        return session.give_back("unsupported", f"stage {stage!r} is not supported yet")
    session.handoff = latest_handoff(shown)
    session.verify()
    session.settle_intents()
    base = prepare_workspace(session.config.repo, workspace_for(session), session.claim.ref)
    session.log("worktree", {"base": base, "workspace": workspace_for(session)})
    result = _run_worker(session, base)
    state_for(session.config).record(session.claim.ref, result)
    return conclude(session, result)


def _run_worker(session: Session, base: str) -> WorkerResult:
    attempt = build_attempt(session, base)
    with Heartbeat(session.awg, session.claim, (_interval(session), attempt.interrupt_file)) as hb:
        session.log("worker_started", {"adapter": attempt.adapter.name})
        result = run_attempt(attempt)
    if hb.lost:
        raise Interrupted("lease_lost", hb.lost)
    session.log("worker_finished", {"outcome": result.outcome,
                                    "candidate": result.candidate_commit})
    return result


def _interval(session: Session) -> float:
    configured = session.config.heartbeat_s
    if configured is not None:
        return configured
    return max(1.0, (session.claim.lease_expires - time.time()) / 3)
