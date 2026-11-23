"""Crash injection for runner recovery tests: a simulated `kill -9` at each stage boundary.

`SimulatedKill` is a BaseException, so none of the runner's `except Exception` handlers (or
its give-back path) run: the process just stops, as with SIGKILL. A fresh `Runner` over the
same state dir and AWG then plays the restarted process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim, EvidenceSpec
from maggy.runner.loop import Runner
from maggy.runner.publish import PublishConfig, Publisher
from maggy.worker import pipeline
from runner_loop_helpers import EDIT_AGENT, Rig, make_rig
from runner_publish_helpers import FakeGh, remote_head
from worker_git_helpers import git

# after worker exit before commit, after commit before evidence, after push before PR,
# after the PR was opened but before its result was recorded, after PR before submit
BOUNDARIES = ["before_commit", "before_evidence", "before_pr", "pr_result", "before_submit"]


class SimulatedKill(BaseException):
    """kill -9 of the runner: nothing after the crash point runs."""


class CrashAwg(FakeAwg):
    crash_at: str | None = None
    submits = 0

    def _crash(self, point: str) -> None:
        if self.crash_at == point:
            self.crash_at = None
            raise SimulatedKill(point)

    def evidence(self, claim: Claim, spec: EvidenceSpec) -> dict:
        self._crash("before_evidence")
        return super().evidence(claim, spec)

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        if ":pr:" in key:
            self._crash("pr_result" if key.endswith(":result") else "before_pr")
        return super().annotate(claim, key, data)

    def submit(self, claim: Claim, summary: str, sha: str) -> dict:
        self._crash("before_submit")
        done = super().submit(claim, summary, sha)
        self.submits += 1
        return done


@dataclass
class CrashRig:
    rig: Rig
    awg: CrashAwg
    gh: FakeGh
    remote: Path


def make_crash_rig(tmp_path: Path, monkeypatch, **options) -> CrashRig:
    """A runner rig with a local bare origin, a fake gh and a Publisher; `options`: agent,
    awg, state_file."""
    awg = options.get("awg") or CrashAwg(lease_seconds=900)
    gh = FakeGh(tmp_path / "ghbin")
    monkeypatch.setenv("PATH", f"{gh.root}:{os.environ['PATH']}")
    publisher = Publisher(awg, PublishConfig(repo=tmp_path / "repo", state_dir=tmp_path / "state"))
    rig = make_rig(tmp_path, options.get("agent", EDIT_AGENT), awg=awg, pr_step=publisher,
                   state_file=options.get("state_file"))
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(rig.repo, "remote", "add", "origin", str(remote))
    return CrashRig(rig, awg, gh, remote)


def crash_once(monkeypatch, name: str) -> None:
    """Make `maggy.worker.pipeline.<name>` die (once) the first time it is called."""
    real, fired = getattr(pipeline, name), []

    def dying(*args):
        if not fired:
            fired.append(name)
            raise SimulatedKill(name)
        return real(*args)

    monkeypatch.setattr(pipeline, name, dying)


def crash(crig: CrashRig, monkeypatch, boundary: str) -> None:
    """Run the first pass and kill it at `boundary`."""
    if boundary == "before_commit":
        crash_once(monkeypatch, "commit_candidate")
    else:
        crig.awg.crash_at = boundary
    with pytest.raises(SimulatedKill):
        crig.rig.runner.run_once()


def restart(crig: CrashRig, passes: int = 3) -> list[str]:
    """A fresh runner process over the same state dir and AWG; the outcome of each pass."""
    runner = Runner(crig.awg, crig.rig.runner.config)
    return [runner.run_once().outcome for _ in range(passes)]


def assert_converged(crig: CrashRig, exact_evidence: bool = True) -> str:
    """One draft PR, evidence bound to the final SHA, one submit; returns that SHA."""
    ref, item = crig.rig.ref, crig.awg.items[crig.rig.ref]
    final = item.revision_sha
    assert item.state == "VERIFYING" and crig.awg.submits == 1
    bound = [(e["kind"], e["commit_sha"]) for e in item.evidence]
    assert bound == [("test", final)] if exact_evidence else {sha for _, sha in bound} == {final}
    [pr] = crig.gh.prs()
    assert crig.gh.creates() == 1 and pr["isDraft"] and pr["head"] == f"maggy/{ref}"
    assert remote_head(crig.remote, ref) == final == git(crig.rig.repo, "rev-parse", f"maggy/{ref}")
    keys = {a["key"] for a in crig.awg.annotations(ref)}
    assert all(f"{key}:result" in keys for key in keys if not key.endswith(":result"))
    return final
