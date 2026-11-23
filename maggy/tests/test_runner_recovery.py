"""Crash recovery: kill -9 at each stage boundary, restart, converge (RFC §2.4, §2.6.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner_crash_helpers import (BOUNDARIES, CrashAwg, SimulatedKill, assert_converged, crash,
                                  crash_once, make_crash_rig, restart)
from worker_git_helpers import git

# Records the prompt it was given and the HEAD it started from, then edits as EDIT_AGENT does.
SEEING_AGENT = """
import json, subprocess, sys
from pathlib import Path
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout
with open(SEEN, "a") as out:
    out.write(json.dumps({"prompt": sys.argv[-1], "head": head.strip()}) + "\\n")
Path("feature.txt").write_text("done\\n")
"""


def held_refs(state_file: Path) -> list[str]:
    return sorted(json.loads(state_file.read_text()).get("held", {})) if state_file.exists() else []


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_crash_at_each_boundary_converges(tmp_path: Path, monkeypatch, boundary: str) -> None:
    state_file = tmp_path / "custom" / "state.json"
    crig = make_crash_rig(tmp_path, monkeypatch, state_file=state_file)
    crash(crig, monkeypatch, boundary)
    assert held_refs(state_file) == [crig.rig.ref], "the held lease was not recorded"
    outcomes = restart(crig)
    assert outcomes.count("submitted") == 1 and outcomes[-1] == "idle", outcomes
    assert_converged(crig)
    assert held_refs(state_file) == []


def test_reclaim_resumes_from_branch_with_handoff_in_prompt(tmp_path: Path, monkeypatch) -> None:
    seen = tmp_path / "seen.jsonl"
    crig = make_crash_rig(tmp_path, monkeypatch, agent=SEEING_AGENT.replace("SEEN", repr(str(seen))))
    base = git(crig.rig.repo, "rev-parse", "HEAD")
    crash_once(monkeypatch, "_checks")  # after the commit, before checks and evidence
    with pytest.raises(SimulatedKill):
        crig.rig.runner.run_once()
    committed = git(crig.rig.repo, "rev-parse", f"maggy/{crig.rig.ref}")
    assert committed != base
    assert restart(crig)[:2] == ["interrupted", "submitted"]
    first, second = [json.loads(line) for line in seen.read_text().splitlines()]
    assert "handoff" not in first["prompt"].lower()
    assert second["head"] == committed, "the re-claim did not resume from the branch"
    assert "[handoff" in second["prompt"] and committed in second["prompt"]
    assert assert_converged(crig) == committed
    [note] = [c["body"] for c in crig.awg.items[crig.rig.ref].comments if "[handoff" in c["body"]]
    assert committed in note and "next" in note.lower()


def test_lease_expired_after_crash_settles_dangling_intent(tmp_path: Path, monkeypatch) -> None:
    now = [1000.0]
    awg = CrashAwg(clock=lambda: now[0], lease_seconds=900)
    crig = make_crash_rig(tmp_path, monkeypatch, awg=awg)
    crash(crig, monkeypatch, "pr_result")
    now[0] += 10_000  # the dead runner's lease lapses
    outcomes = restart(crig)
    assert outcomes.count("submitted") == 1 and outcomes[-1] == "idle", outcomes
    assert_converged(crig, exact_evidence=False)
    settled = [a["data"] for a in awg.annotations(crig.rig.ref)
               if a["key"].endswith(":result") and a["data"].get("reconciled")]
    assert [(d["action"], d["number"]) for d in settled] == [("pr", 1)]


def test_reconcile_does_nothing_while_stop_is_set(tmp_path: Path, monkeypatch) -> None:
    crig = make_crash_rig(tmp_path, monkeypatch)
    crash(crig, monkeypatch, "before_submit")
    (crig.rig.state / "STOP").write_text("stop\n")
    assert restart(crig, passes=1) == ["stopped"]
    assert crig.awg.submits == 0 and crig.awg.items[crig.rig.ref].state == "ACTIVE"
    default_state = crig.rig.state / "runner" / "state.json"
    assert held_refs(default_state) == [crig.rig.ref]
