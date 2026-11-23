"""Crash recovery kills the dead runner's orphaned worker group; `stop` kills only a group
whose leader is still the recorded process (RFC §2.6.3, §2.6.8)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from maggy.runner.control import pid_dir, request_stop
from maggy.runner.loop import Runner
from maggy.runner.state import state_for
from maggy.worker.pidfile import write_pid_file
from runner_loop_helpers import CAPS, EDIT_AGENT, make_rig

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def _orphan() -> subprocess.Popen:
    return subprocess.Popen(SLEEPER, start_new_session=True)


def test_reconcile_kills_the_orphaned_worker_and_unlinks_its_pid_file(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    claim = rig.awg.next_claim([*CAPS, "project:demo"])  # the crashed runner's lease
    state_for(rig.runner.config).hold(claim)
    orphan, pid_file = _orphan(), pid_dir(rig.state) / f"{claim.attempt_id}.pid"
    try:
        write_pid_file(pid_file, orphan.pid)
        report = Runner(rig.awg, rig.runner.config).run_once()
        assert report.outcome == "interrupted"
        assert orphan.wait(timeout=10) != 0, "the orphaned worker is still running"
    finally:
        orphan.kill()
    assert not pid_file.exists()


def test_stop_does_not_kill_a_process_that_reused_the_pid(tmp_path: Path) -> None:
    other = _orphan()
    pid_file = pid_dir(tmp_path) / "att-1.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text(f"{other.pid} Mon Jan  1 00:00:00 2001\n")  # a different process
    try:
        assert request_stop(tmp_path) == 0
        assert other.poll() is None, "stop killed an unrelated process group"
    finally:
        other.kill()


def test_stop_refuses_a_pid_file_without_identity(tmp_path: Path) -> None:
    other = _orphan()
    pid_file = pid_dir(tmp_path) / "att-1.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text(f"{other.pid}\n")
    try:
        assert request_stop(tmp_path) == 0 and other.poll() is None
    finally:
        other.kill()
