"""`maggy worker replay` CLI: offline table + JSON report, task validation."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from maggy.cli import app
from maggy.worker.replay.report import ReplayReport


def test_cli_prints_table_and_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    args = ["worker", "replay", "--agents", "claude,codex", "--tasks", "implement,ambiguous",
            "--work-dir", str(tmp_path / "w"), "--json", str(out)]
    run = CliRunner().invoke(app, args)
    assert run.exit_code == 0, run.output
    assert "implement" in run.stdout and "ambiguous" in run.stdout
    report = ReplayReport.model_validate_json(out.read_text())
    assert [(r.task, r.agent, r.verdict) for r in report.rows] == [
        ("implement", "claude", "pass"), ("implement", "codex", "pass"),
        ("ambiguous", "claude", "pass"), ("ambiguous", "codex", "pass")]


def test_cli_rejects_unknown_task(tmp_path: Path) -> None:
    run = CliRunner().invoke(app, ["worker", "replay", "--tasks", "nope",
                                   "--work-dir", str(tmp_path / "w")])
    assert run.exit_code == 2 and "nope" in run.output
