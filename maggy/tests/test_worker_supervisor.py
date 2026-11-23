"""Process supervisor: process groups, deadline, kill switch, streaming cost (RFC §2.6.3/4/8)."""

from __future__ import annotations

import sys
import threading
import time

from maggy.worker.supervisor import supervise
from worker_supervisor_helpers import GRANDCHILD, PI_COST, job, marker_job, pid_gone, script


def test_normal_exit_streams_logs_into_attempt_dir(tmp_path):
    run = supervise(marker_job(tmp_path))
    assert run.outcome == "succeeded" and run.exit_code == 0 and run.launched
    assert run.stdout_log.parent == tmp_path / "attempt"
    assert "hello out" in run.stdout_log.read_text()
    assert "hello err" in run.stderr_log.read_text()


def test_nonzero_exit_is_failed(tmp_path):
    run = supervise(job(tmp_path, [sys.executable, "-c", "raise SystemExit(3)"]))
    assert run.outcome == "failed" and run.exit_code == 3


def test_deadline_kills_the_whole_group_including_grandchild(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    argv = [sys.executable, str(script(tmp_path, "gc", GRANDCHILD)), str(pid_file)]
    started = time.monotonic()
    run = supervise(job(tmp_path, argv, deadline_s=1.0))
    assert run.outcome == "timeout" and run.reason == "deadline"
    assert time.monotonic() - started < 10
    assert pid_gone(int(pid_file.read_text()))


def test_stop_file_prevents_launch(tmp_path):
    (tmp_path / "STOP").write_text("")
    run = supervise(marker_job(tmp_path))
    assert run.outcome == "failed" and run.reason == "stopped" and not run.launched
    assert not (tmp_path / "ran.txt").exists()


def test_stop_file_kills_a_running_worker(tmp_path):
    threading.Timer(0.5, (tmp_path / "STOP").write_text, args=("",)).start()
    started = time.monotonic()
    run = supervise(marker_job(tmp_path, sleep_s=60))
    assert run.outcome == "failed" and run.reason == "stopped" and run.launched
    assert time.monotonic() - started < 10


def test_streaming_cost_overspend_kills_with_budget_exceeded(tmp_path):
    argv = [sys.executable, str(script(tmp_path, "pi", PI_COST))]
    started = time.monotonic()
    run = supervise(job(tmp_path, argv, parser="pi-jsonl", cost_limit_usd=0.2))
    assert run.outcome == "budget_exceeded"
    assert run.cost_usd is not None and run.cost_usd > 0.2
    assert time.monotonic() - started < 8


def test_final_cost_parsed_without_streaming_limit(tmp_path):
    code = "import json; print(json.dumps({'type':'result','total_cost_usd':0.3,'result':'ok'}))"
    run = supervise(job(tmp_path, [sys.executable, "-c", code], parser="claude-json"))
    assert run.outcome == "succeeded" and run.cost_usd == 0.3


def test_default_stop_file_is_under_maggy_home(tmp_path):
    spec = job(tmp_path, ["true"])
    from maggy.worker.supervisor import Job
    default = Job(run_id="r", argv=["true"], cwd=tmp_path, env={},
                  attempt_dir=tmp_path, deadline_s=1.0)
    assert default.stop_file.name == "STOP" and default.stop_file.parent.name == ".maggy"
    assert spec.stop_file == tmp_path / "STOP"
