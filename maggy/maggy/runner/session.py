"""One claimed item: its decision log, fence verification and the report it ends with."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from maggy.runner.awg_client import AwgClient
from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_types import Claim
from maggy.runner.config import RunnerConfig
from maggy.runner.control import stop_file


class Stopped(Exception):
    """The kill switch was pulled mid-attempt."""


def verify_live(awg: AwgClient, claim: Claim, state_dir: Path) -> None:
    """STOP not pulled and `claim` still the live fence (Stopped / LeaseLost otherwise)."""
    if stop_file(state_dir).exists():
        raise Stopped("STOP file present")
    awg.heartbeat(claim)


@dataclass(frozen=True)
class RunReport:
    """outcome: idle, stopped, paused, submitted, waiting_human, interrupted, spec_review,
    unsupported or failed."""

    outcome: str
    ref: str | None = None
    spec_version: int | None = None
    detail: str = ""


@dataclass
class Session:
    awg: AwgClient
    claim: Claim
    config: RunnerConfig
    events: list[str] = field(default_factory=list)
    handoff: str = ""  # the previous attempt's handoff, passed to the worker prompt

    @property
    def attempt_dir(self) -> Path:
        return self.config.state_dir / "attempts" / self.claim.attempt_id

    def log(self, event: str, data: dict | None = None) -> None:
        """Append one decision to <attempt dir>/runner.jsonl."""
        self.attempt_dir.mkdir(parents=True, exist_ok=True)
        record = {"at": time.time(), "event": event, "ref": self.claim.ref, **(data or {})}
        with (self.attempt_dir / "runner.jsonl").open("a") as out:
            out.write(json.dumps(record, default=str) + "\n")
        self.events.append(event)

    def verify(self) -> None:
        """Before any side effect: STOP not pulled and our fence still live (raises)."""
        verify_live(self.awg, self.claim, self.config.state_dir)

    def settle_intents(self) -> None:
        """Let the PR step record results for intents a crashed runner left dangling."""
        settle = getattr(self.config.pr_step, "settle", None)
        if callable(settle):
            settle(self.claim)

    def give_back(self, outcome: str, reason: str) -> RunReport:
        """Release the item with a handoff; an AWG failure here is logged, not raised."""
        self.log(outcome, {"reason": reason})
        for call in (lambda: self.awg.release(self.claim, reason),
                     lambda: self.awg.handoff(self.claim, f"{outcome}: {reason}")):
            try:
                call()
            except AwgError as exc:
                self.log("awg_error", {"error": str(exc)})
        return self.report(outcome, reason)

    def report(self, outcome: str, detail: str = "") -> RunReport:
        return RunReport(outcome, self.claim.ref, self.claim.version, detail)
