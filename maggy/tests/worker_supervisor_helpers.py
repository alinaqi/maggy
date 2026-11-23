"""Fake worker CLIs (small python scripts) and helpers for supervisor tests."""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.ledger import BudgetLedger, BudgetRefused
from maggy.worker.supervisor import Job
from worker_helpers import adapter_data

GRANDCHILD = """
import os, signal, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c",
    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)"])
open(sys.argv[1], "w").write(str(child.pid))
signal.signal(signal.SIGTERM, signal.SIG_IGN)
time.sleep(120)
"""

MARKER = """
import sys, time
open(sys.argv[1], "w").write("ran")
print("hello out"); print("hello err", file=sys.stderr)
time.sleep(float(sys.argv[2]))
"""

PI_COST = """
import json, sys, time
for _ in range(200):
    usage = {"cost": {"total": 0.05}, "input": 1, "output": 1}
    print(json.dumps({"type": "message_end", "message": {"role": "assistant",
          "usage": usage, "content": "x"}}), flush=True)
    time.sleep(0.05)
"""


def script(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(textwrap.dedent(body))
    return path


def job(tmp_path: Path, argv: list[str], **overrides) -> Job:
    fields = {"run_id": "run-1", "argv": argv, "cwd": tmp_path, "env": dict(os.environ),
              "attempt_dir": tmp_path / "attempt", "deadline_s": 30.0,
              "stop_file": tmp_path / "STOP", "grace_s": 0.5, "poll_s": 0.05}
    return Job(**(fields | overrides))


def marker_job(tmp_path: Path, sleep_s: float = 0.0, **overrides) -> Job:
    path = script(tmp_path, "marker", MARKER)
    argv = [sys.executable, str(path), str(tmp_path / "ran.txt"), str(sleep_s)]
    return job(tmp_path, argv, **overrides)


def pid_gone(pid: int, wait_s: float = 5.0) -> bool:
    """True once `pid` no longer exists (orphans are reaped by init)."""
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def reserve_many(args: tuple[str, int, float]) -> int:
    """Process-pool entry: try `count` reservations; return how many succeeded."""
    db, count, amount = args
    ledger = BudgetLedger(Path(db), per_day_usd=1.0)
    granted = 0
    for n in range(count):
        try:
            ledger.reserve(f"{os.getpid()}-{n}", amount)
            granted += 1
        except BudgetRefused:
            pass
    return granted


def cost_adapter(streams: bool, fixed: float | None) -> AdapterSpec:
    cost = {"streams": streams, "fixed_reservation_usd": fixed}
    return AdapterSpec.model_validate(adapter_data(cost=cost))
