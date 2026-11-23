"""Read-only stage workers (spec, later plan): one fresh agent run per question (RFC §2.5).

Each call is its own attempt (own id, attempt dir, budget reservation and CLI process), so
the reviewer never shares a session with the author. The run is read_only and heartbeated
like a build; lease loss raises LeaseLost so `drive.guarded` gives the item back.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

from maggy.runner.awg_errors import LeaseLost
from maggy.runner.config import RunnerConfig
from maggy.runner.control import pid_dir
from maggy.runner.heartbeat import Heartbeat
from maggy.runner.session import Session
from maggy.runner.workspace import safe_name
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.models import Stage, WorkerSpec
from maggy.worker.parsers import RawRun, parse_run
from maggy.worker.pipeline import Attempt, run_attempt

PERMISSION = "read_only"
RAN = ("succeeded", "blocked")  # a QUESTION: line is still an answer the stage parses


class StageFailed(RuntimeError):
    """The stage worker did not produce a reply."""


def role_adapter(config: RunnerConfig, role: str) -> AdapterSpec:
    """`agents.prefer.<role>` (review only), else `agents.default`, else the runner's adapter."""
    agents = config.profile.agents
    name = (agents.prefer.get(role) if role == "review" else None) or agents.default
    return config.adapters.get(name or "", config.adapter)


def heartbeat_interval(session: Session) -> float:
    configured = session.config.heartbeat_s
    if configured is not None:
        return configured
    return max(1.0, (session.claim.lease_expires - time.time()) / 3)


@dataclass
class StageWorkers:
    session: Session
    stage: Stage
    workspace: tuple[Path, str]  # (worktree, base commit)
    _runs: count = field(default_factory=lambda: count(1))

    def ask(self, role: str, prompt: str) -> str:
        """Run the `role` agent once on `prompt` (read-only) and return its final text."""
        attempt = self._attempt(role, prompt)
        with Heartbeat(self.session.awg, self.session.claim,
                       (heartbeat_interval(self.session), attempt.interrupt_file)) as hb:
            self.session.log("stage_worker", {"role": role, "adapter": attempt.adapter.name})
            result = run_attempt(attempt)
        if hb.lost:
            raise LeaseLost("lease_lost", hb.lost)
        if result.outcome not in RAN:
            raise StageFailed(f"{role} worker {result.outcome}")
        return _final_text(attempt)

    def _attempt(self, role: str, prompt: str) -> Attempt:
        session, (worktree, base) = self.session, self.workspace
        claim, config = session.claim, session.config
        run_id = safe_name(f"{claim.attempt_id}-{self.stage}-{role}-{next(self._runs)}")
        spec = WorkerSpec(awg_ref=claim.ref, attempt_id=run_id,
                          fencing_token=str(claim.fencing_token), stage=self.stage,
                          repo=config.repo, base_commit=base, spec_version=claim.version,
                          workspace=worktree, permission=PERMISSION,
                          deadline_s=config.profile.worker.timeout_minutes * 60,
                          budget_usd=config.profile.budget.per_run_usd or 0.0, prompt=prompt)
        return Attempt(spec=spec, adapter=role_adapter(config, role), profile=config.profile,
                       state_dir=config.state_dir, interrupt_file=session.attempt_dir / "INTERRUPT",
                       pid_file=pid_dir(config.state_dir) / f"{run_id}.pid")


def _final_text(attempt: Attempt) -> str:
    """The agent's final reply, parsed from the attempt's stdout like any worker run."""
    stdout = attempt.attempt_dir / "stdout.log"
    text = stdout.read_text(errors="replace") if stdout.exists() else ""
    parsed = parse_run(attempt.adapter.output, RawRun(stdout=text), attempt.adapter.quota_patterns)
    if parsed.error:
        raise StageFailed(f"unparseable {attempt.adapter.name} output: {parsed.error}")
    return parsed.final_text
