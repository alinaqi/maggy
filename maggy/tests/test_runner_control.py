"""Kill switch and intake pause (RFC §2.6.8): STOP, `maggy run stop`, `maggy run pause`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from maggy.runner.cli import app
from maggy.runner.control import is_paused, pid_dir, stop_file
from runner_loop_helpers import EDIT_AGENT, make_rig


def _cli() -> typer.Typer:
    root = typer.Typer()
    root.add_typer(app, name="run")
    return root


def test_stop_file_prevents_claim(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    stop_file(rig.state).parent.mkdir(parents=True, exist_ok=True)
    stop_file(rig.state).write_text("stop\n")
    assert rig.runner.run_once().outcome == "stopped"
    assert rig.awg.items[rig.ref].state == "READY"


def test_run_stop_creates_stop_and_kills_registered_groups(tmp_path: Path) -> None:
    state = tmp_path / "state"
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            start_new_session=True)
    pid_dir(state).mkdir(parents=True)
    (pid_dir(state) / "att-1.pid").write_text(f"{proc.pid}\n")
    try:
        result = CliRunner().invoke(_cli(), ["run", "stop", "--state-dir", str(state)])
        assert result.exit_code == 0, result.output
        assert proc.wait(timeout=10) != 0, "the worker group was not killed"
    finally:
        proc.kill()
    assert stop_file(state).exists()


def test_run_pause_pauses_intake_for_project(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, project="K")
    result = CliRunner().invoke(_cli(), ["run", "pause", "--project", "K",
                                         "--state-dir", str(rig.state)])
    assert result.exit_code == 0, result.output
    assert is_paused(rig.state, "K") and not is_paused(rig.state, "other")
    assert rig.runner.run_once().outcome == "paused"
    assert rig.awg.items[rig.ref].state == "READY"
    resumed = CliRunner().invoke(_cli(), ["run", "resume", "--project", "K",
                                          "--state-dir", str(rig.state)])
    assert resumed.exit_code == 0 and not is_paused(rig.state, "K")


def test_run_once_without_adapter_is_refused(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    result = CliRunner().invoke(_cli(), ["run", "--once", "--repo", str(tmp_path),
                                         "--state-dir", str(tmp_path / "state")])
    assert result.exit_code == 2 and "no adapter" in result.output
