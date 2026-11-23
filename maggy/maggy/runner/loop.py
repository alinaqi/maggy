"""The runner loop (`maggy run`): kill switch, pause, claim, drive (RFC §2.4, §2.6.8)."""

from __future__ import annotations

import time

from maggy.runner.awg_client import AwgClient
from maggy.runner.config import CAPABILITIES, RunnerConfig
from maggy.runner.control import is_paused, stop_file
from maggy.runner.drive import drive
from maggy.runner.session import RunReport, Session

__all__ = ["CAPABILITIES", "RunReport", "Runner", "RunnerConfig"]


class Runner:
    def __init__(self, awg: AwgClient, config: RunnerConfig) -> None:
        self.awg, self.config = awg, config

    def run_once(self) -> RunReport:
        """At most one item: nothing is claimed while STOP exists or the project is paused."""
        state = self.config.state_dir
        if stop_file(state).exists():
            return RunReport("stopped")
        if is_paused(state, self.config.project):
            return RunReport("paused")
        claim = self.awg.next_claim(list(CAPABILITIES))
        if claim is None:
            return RunReport("idle")
        session = Session(self.awg, claim, self.config)
        session.log("claimed", {"attempt": claim.attempt_id, "spec_version": claim.version,
                                "fencing_token": claim.fencing_token})
        return drive(session)

    def run(self, once: bool = False, idle_s: float = 30.0) -> list[RunReport]:
        """Loop until STOP (or after one pass with `once`); sleeps when idle or paused."""
        reports: list[RunReport] = []
        while True:
            report = self.run_once()
            reports.append(report)
            if once or report.outcome == "stopped":
                return reports
            if report.outcome in ("idle", "paused"):
                time.sleep(idle_s)
