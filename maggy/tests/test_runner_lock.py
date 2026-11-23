"""One runner per state dir: a second `maggy run` must not reconcile a live runner's leases."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.lock import RunnerLock, lock_path
from maggy.runner.loop import Runner
from maggy.runner.state import state_for
from runner_loop_helpers import CAPS, EDIT_AGENT, make_rig


def test_second_runner_leaves_a_live_runners_lease_alone(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    with RunnerLock(lock_path(rig.state)):  # the first, live runner
        claim = rig.awg.next_claim([*CAPS, "project:demo"])
        state_for(rig.runner.config).hold(claim)
        report = rig.runner.run_once()
        assert report.outcome == "locked", report
        assert rig.awg.items[rig.ref].state == "ACTIVE"
        rig.awg.heartbeat(claim)  # still the live lease
        assert rig.runner.run(once=False) == [report]
    assert [ref for ref in _held(rig)] == [rig.ref], "the live runner's entry was dropped"


def test_runner_lock_is_released_after_a_pass(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    assert rig.runner.run_once().outcome == "submitted"
    assert Runner(rig.awg, rig.runner.config).run_once().outcome == "idle"


def test_runner_lock_is_reentrant_within_one_runner(tmp_path: Path) -> None:
    lock = RunnerLock(lock_path(tmp_path))
    with lock, lock:
        assert lock.held
    assert not lock.held


def _held(rig) -> list[str]:
    return [claim.ref for claim, _ in state_for(rig.runner.config).held()]
