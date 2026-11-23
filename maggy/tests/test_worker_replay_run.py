"""`maggy worker replay`: every task x agent through the real pipeline, offline and live."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from maggy.worker.replay.fake import RECORDINGS
from maggy.worker.replay.report import ReplayReport, render_table
from maggy.worker.replay.runner import ReplayOptions, run_replay

AGENTS = ["claude", "codex", "opencode", "pi"]
TASKS = ["implement", "off_by_one", "cli_flag", "refactor", "ambiguous"]


@pytest.fixture(scope="module")
def offline(tmp_path_factory: pytest.TempPathFactory) -> ReplayReport:
    work = tmp_path_factory.mktemp("replay")
    return run_replay(ReplayOptions(agents=AGENTS, tasks=TASKS, work_dir=work))


def _rows(report: ReplayReport, task: str):
    return [row for row in report.rows if row.task == task]


def test_offline_runs_every_task_for_every_agent(offline: ReplayReport) -> None:
    assert offline.mode == "offline"
    assert [(r.task, r.agent) for r in offline.rows] == [(t, a) for t in TASKS for a in AGENTS]
    assert {row.verdict for row in offline.rows} == {"pass"}


def test_offline_rows_are_comparable_across_agents(offline: ReplayReport) -> None:
    for task in TASKS[:4]:
        rows = _rows(offline, task)
        assert {(r.outcome, r.checks_passed, r.checks_total) for r in rows} == {
            ("succeeded", 2, 2)}
        assert len({tuple(r.changed_files) for r in rows}) == 1 and rows[0].changed_files
    for row in _rows(offline, "ambiguous"):
        assert (row.outcome, row.changed_files, row.checks_total) == ("blocked", [], 0)
        assert row.blocker and row.blocker.startswith("What are the new discount rules")


def test_offline_rows_carry_parsed_cost_and_model(offline: ReplayReport) -> None:
    by_agent = {row.agent: row for row in _rows(offline, "implement")}
    assert (by_agent["claude"].model, by_agent["claude"].cost_usd) == ("claude-haiku-5-5",
                                                                      0.00192536)
    assert by_agent["pi"].model == "claude-haiku-4-5" and by_agent["codex"].model == "unknown"
    assert all(row.elapsed_s > 0 for row in offline.rows)


def test_offline_fakes_ran_the_shipped_adapter_argv(offline: ReplayReport) -> None:
    calls = (offline.work_dir / "implement-claude" / "bin" / "calls.jsonl").read_text()
    [argv] = [json.loads(line) for line in calls.splitlines()]
    assert argv[:2] == ["-p", "--no-session-persistence"] and "acceptEdits" in argv
    assert argv[argv.index("--max-budget-usd") + 1] == "0.2500"


def test_table_and_json_report(offline: ReplayReport) -> None:
    lines = render_table(offline).splitlines()
    for column in ("task", "agent", "verdict", "outcome", "checks", "changed", "cost",
                   "elapsed", "model"):
        assert column in lines[0]
    assert len([line for line in lines if " pass " in line]) == 20
    assert ReplayReport.model_validate_json(offline.model_dump_json()) == offline


def _fake_cli_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in `claude` on PATH that asks a question and leaves a marker file."""
    bindir, marker = tmp_path / "realbin", tmp_path / "invoked"
    bindir.mkdir()
    reply = (RECORDINGS / "claude.json").read_text().replace('"done"', '"QUESTION: Which?"')
    script = bindir / "claude"
    script.write_text(f"#!{sys.executable}\nimport pathlib, sys\n"
                      f"pathlib.Path({str(marker)!r}).write_text('x')\n"
                      f"sys.stdout.write({reply!r})\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{Path(sys.executable).parent}:/usr/bin:/bin")
    return marker


def test_live_runs_the_cli_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = _fake_cli_on_path(tmp_path, monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # a personal profile for this test only
    personal = tmp_path / "home" / ".maggy" / "harness.yaml"
    personal.parent.mkdir(parents=True)
    personal.write_text("worker: {allow_host_execution: true}\n")
    opts = ReplayOptions(agents=["claude"], tasks=["ambiguous"], live=True,
                         work_dir=tmp_path / "w", state_dir=tmp_path / "state")
    [row] = run_replay(opts).rows
    assert marker.exists() and not (tmp_path / "w" / "ambiguous-claude" / "bin").exists()
    assert (row.verdict, row.outcome, row.blocker) == ("pass", "blocked", "Which?")


@pytest.mark.parametrize("case", [("opencode", "no native sandbox"),
                                  ("claude", "required checks")])
def test_live_refuses_without_host_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                          case: tuple[str, str]) -> None:
    """opencode: no native sandbox; claude: its required checks would lack a boundary."""
    agent, why = case
    marker = _fake_cli_on_path(tmp_path, monkeypatch)
    opts = ReplayOptions(agents=[agent], tasks=["implement"], live=True,
                         work_dir=tmp_path / "w", state_dir=tmp_path / "state")
    [row] = run_replay(opts).rows
    assert (row.verdict, row.outcome) == ("refused", None) and not marker.exists()
    assert why in (row.reason or "") and "allow_host_execution" in (row.reason or "")
