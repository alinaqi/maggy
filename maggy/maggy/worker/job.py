"""What the supervisor runs, and what it reports back."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from maggy.worker.models import Outcome


def default_stop_file() -> Path:
    """The kill switch: `~/.maggy/STOP` (RFC §2.6.8)."""
    return Path.home() / ".maggy" / "STOP"


@dataclass(frozen=True)
class Job:
    """One worker process. `cost_limit_usd` is set only for cost-streaming adapters."""

    run_id: str
    argv: list[str]
    cwd: Path
    env: dict[str, str]
    attempt_dir: Path
    deadline_s: float
    parser: str = "text"
    cost_limit_usd: float | None = None
    stop_file: Path = field(default_factory=default_stop_file)
    grace_s: float = 5.0
    poll_s: float = 0.1

    @property
    def stdout_log(self) -> Path:
        return self.attempt_dir / "stdout.log"

    @property
    def stderr_log(self) -> Path:
        return self.attempt_dir / "stderr.log"


@dataclass(frozen=True)
class Supervised:
    """How the process ended. `reason` is 'deadline', 'stopped', 'budget' or 'exit code N'."""

    outcome: Outcome
    reason: str | None
    launched: bool
    exit_code: int | None
    elapsed_s: float
    cost_usd: float | None
    stdout_log: Path
    stderr_log: Path
