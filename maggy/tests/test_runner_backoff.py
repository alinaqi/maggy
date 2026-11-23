"""A failing item is not re-run in a hot loop: backoff after every non-progress pass and a
cap on consecutive failed attempts, after which the item waits for a human."""

from __future__ import annotations

from pathlib import Path

from maggy.runner import loop
from maggy.runner.retry import trailing_failures
from runner_loop_helpers import EDIT_AGENT, decisions, make_rig


def test_failing_item_backs_off_and_is_blocked_after_the_cap(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, check_exit=1)
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 4:
            (rig.state / "STOP").write_text("stop\n")

    monkeypatch.setattr(loop, "sleep", fake_sleep)
    outcomes = [r.outcome for r in rig.runner.run(once=False, idle_s=30)]
    assert outcomes == ["failed", "failed", "failed", "waiting_human", "idle", "stopped"]
    assert sleeps == [30, 30, 30, 30]
    assert rig.awg.items[rig.ref].state == "WAITING_HUMAN"
    assert decisions(rig).count("worker_started") == 3


def test_trailing_failures_skip_interruptions_and_stop_at_other_comments() -> None:
    bodies = ["[handoff a1] failed: x", "a human: try again", "[handoff a2] failed: y",
              "[handoff a3] interrupted: lease", "[handoff a4] unsupported: stage"]
    assert trailing_failures({"comments": [{"body": b} for b in bodies]}) == 2
    assert trailing_failures({}) == 0
