"""Turn a finished attempt into its WorkerResult: outcome, blocker, cost (RFC §2.3)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from maggy.worker.blocker import agent_blocker
from maggy.worker.job import Supervised
from maggy.worker.models import CheckResult, Outcome, WorkerResult
from maggy.worker.parsers import ParsedRun, RawRun, parse_run
from maggy.worker.protected import protected_blocker, protected_paths

if TYPE_CHECKING:
    from maggy.worker.commit import Candidate
    from maggy.worker.pipeline import Attempt


def build_result(attempt: Attempt, run: Supervised,
                 found: tuple[Candidate, list[CheckResult]]) -> WorkerResult:
    candidate, checks = found
    adapter = attempt.adapter
    parsed = parse_run(adapter.output, raw_run(run), adapter.quota_patterns)
    blocker = (protected_blocker(protected_paths(candidate.changed_files, attempt.profile))
               or agent_blocker(parsed.final_text))
    return WorkerResult(outcome=outcome(run, parsed, blocker is not None),
                        candidate_commit=candidate.commit,
                        changed_files=candidate.changed_files, checks=checks,
                        artifacts=[str(run.stdout_log), str(run.stderr_log)], blocker=blocker,
                        cost_usd=run.cost_usd or parsed.cost_usd or 0.0, elapsed_s=run.elapsed_s,
                        agent=adapter.name, model=parsed.model or attempt.model or "unknown",
                        adapter_version=adapter.tested_version or "unknown")


def outcome(run: Supervised, parsed: ParsedRun, blocked: bool) -> Outcome:
    """The CLI's own budget stop is budget_exceeded, not an ordinary (retryable) failure."""
    if run.outcome == "failed" and run.reason != "stopped" and parsed.budget_hit:
        return "budget_exceeded"
    return "blocked" if blocked and run.outcome == "succeeded" else run.outcome


def raw_run(run: Supervised) -> RawRun:
    return RawRun(stdout=_read(run.stdout_log), stderr=_read(run.stderr_log),
                  exit_code=run.exit_code)


def _read(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""
