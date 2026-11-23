"""Replay report: one comparable row per task x agent, as a table and as JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from maggy.harness.schema_sections import Strict
from maggy.worker.models import Outcome, WorkerResult
from maggy.worker.replay.tasks import ReplayTask

Verdict = Literal["pass", "fail", "refused"]
COLUMNS = ("task", "agent", "verdict", "outcome", "checks", "changed", "cost", "elapsed",
           "model")


class ReplayRow(Strict):
    task: str
    agent: str
    expect: Literal["pass", "blocker"]
    verdict: Verdict
    outcome: Outcome | None = None
    checks_passed: int = 0
    checks_total: int = 0
    changed_files: list[str] = []
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    model: str = "-"
    adapter_version: str = "-"
    blocker: str | None = None
    reason: str | None = None


class ReplayReport(Strict):
    mode: Literal["offline", "live"]
    work_dir: Path
    rows: list[ReplayRow] = []


def verdict(task: ReplayTask, result: WorkerResult) -> Verdict:
    """pass: checks all green on a candidate, or (blocker tasks) a question and no edits."""
    if task.expect == "blocker":
        ok = result.outcome == "blocked" and result.candidate_commit is None
    else:
        ok = (result.outcome == "succeeded" and bool(result.checks)
              and all(check.passed for check in result.checks))
    return "pass" if ok else "fail"


def result_row(task: ReplayTask, result: WorkerResult) -> ReplayRow:
    passed = sum(check.passed for check in result.checks)
    return ReplayRow(task=task.id, agent=result.agent, expect=task.expect,
                     verdict=verdict(task, result), outcome=result.outcome,
                     checks_passed=passed, checks_total=len(result.checks),
                     changed_files=result.changed_files, cost_usd=result.cost_usd,
                     elapsed_s=result.elapsed_s, model=result.model,
                     adapter_version=result.adapter_version,
                     blocker=result.blocker.question if result.blocker else None)


def refused_row(task: ReplayTask, agent: str, reason: str) -> ReplayRow:
    return ReplayRow(task=task.id, agent=agent, expect=task.expect, verdict="refused",
                     reason=reason)


def _cells(row: ReplayRow) -> list[str]:
    return [row.task, row.agent, row.verdict, row.outcome or "-",
            f"{row.checks_passed}/{row.checks_total}", ",".join(row.changed_files) or "-",
            f"${row.cost_usd:.4f}", f"{row.elapsed_s:.1f}s", row.model]


def render_table(report: ReplayReport) -> str:
    """A fixed-width comparison table; refusal reasons are listed below it."""
    grid = [list(COLUMNS), *(_cells(row) for row in report.rows)]
    widths = [max(len(line[i]) for line in grid) for i in range(len(COLUMNS))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip()
             for line in grid]
    notes = [f"{row.task}/{row.agent}: {row.reason}" for row in report.rows if row.reason]
    return "\n".join([*lines, *notes])
