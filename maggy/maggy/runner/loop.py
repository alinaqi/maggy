"""The runner loop (`maggy run`): kill switch, pause, claim, drive (RFC §2.4, §2.6.8).

One runner per state dir (`RunnerLock`): a second one reports `locked` and touches nothing.
Every pass that made no progress (idle, paused, failed, unsupported, interrupted, ...) is
followed by a backoff sleep, so a failing item is never re-run in a hot loop.
"""

from __future__ import annotations

from time import sleep

from maggy.runner.awg_client import AwgClient
from maggy.runner.config import CAPABILITIES, RunnerConfig, claim_capabilities
from maggy.runner.control import is_paused, stop_file
from maggy.runner.drive import drive
from maggy.runner.lock import Locked, RunnerLock, lock_path
from maggy.runner.recovery import reconcile
from maggy.runner.session import RunReport, Session
from maggy.runner.state import state_for

__all__ = ["CAPABILITIES", "RunReport", "Runner", "RunnerConfig"]
PROGRESS = frozenset({"submitted", "waiting_human", "spec_review", "spec_approved"})


class Runner:
    def __init__(self, awg: AwgClient, config: RunnerConfig) -> None:
        self.awg, self.config = awg, config
        self.lock = RunnerLock(lock_path(config.state_dir))

    def run_once(self) -> RunReport:
        """One pass under the state-dir lock; `locked` when another runner holds it."""
        try:
            with self.lock:
                return self._pass()
        except Locked as exc:
            return RunReport("locked", detail=str(exc))

    def _pass(self) -> RunReport:
        """Reconcile leases a crashed run left, else at most one item: nothing is claimed
        (or reconciled) while STOP exists, and nothing is claimed while the project is paused.
        Claims are bound to `config.project` (`project:<key>`), so another project's items
        (paused or not) are never claimed here."""
        state = self.config.state_dir
        if stop_file(state).exists():
            return RunReport("stopped")
        recovered = reconcile(self.awg, self.config)
        if recovered:
            return recovered[-1]
        if is_paused(state, self.config.project):
            return RunReport("paused")
        return self._claim_and_drive()

    def _claim_and_drive(self) -> RunReport:
        claim = self.awg.next_claim(*claim_capabilities(self.config.project))
        if claim is None:
            return RunReport("idle")
        held = state_for(self.config)
        held.hold(claim)
        session = Session(self.awg, claim, self.config)
        session.log("claimed", {"attempt": claim.attempt_id, "spec_version": claim.version,
                                "fencing_token": claim.fencing_token})
        report = drive(session)
        held.drop(claim.ref)  # not in a finally: a killed runner must leave the lease recorded
        return report

    def run(self, once: bool = False, idle_s: float = 30.0) -> list[RunReport]:
        """Loop until STOP (or after one pass with `once`), holding the lock throughout."""
        try:
            with self.lock:
                return self._loop(once, idle_s)
        except Locked as exc:
            return [RunReport("locked", detail=str(exc))]

    def _loop(self, once: bool, idle_s: float) -> list[RunReport]:
        reports: list[RunReport] = []
        while True:
            report = self.run_once()
            reports.append(report)
            if once or report.outcome in ("stopped", "locked"):
                return reports
            if report.outcome not in PROGRESS:
                sleep(idle_s)  # backoff: never re-run a failing item in a hot loop
