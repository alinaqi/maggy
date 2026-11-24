"""The coupon scenario rig: the Phase 4 exit rig (REAL awg in a temp HOME/AWG_HOME, local
bare origin, fake gh, replay spec/plan agents) with the buggy checkout on main, a build agent
that applies the real fix diff, a pytest+Playwright regression runner and the human steps.

Build runs go through `maggy run --once` (a subprocess, like the earlier exit tests); verify
runs in-process from the same `build_runner` so the vision reviewer and the review council
can be fakes (Ollama is not installed here; a missing backend is PENDING, never PASS).
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from dataclasses import replace

from coupon_helpers import build_agent_source, seed_app
from runner_exit_helpers import ExitRig
from worker_git_helpers import fake_adapter_data, git, write_script
from worker_helpers import write_adapter

from maggy.review.models import Verdict
from maggy.runner.awg_types import annotation_key
from maggy.runner.cli_setup import RunCliOptions, build_runner
from maggy.runner.loop import Runner
from maggy.runner.session import RunReport

STATIC = shlex.join([sys.executable, "check_static.py"])


class FakeCouncil:
    """A review council with no findings that records what it was fed."""

    def __init__(self) -> None:
        self.requests: list = []

    def review(self, request: object) -> Verdict:
        self.requests.append(request)
        return Verdict(decision="approve", summary="Spec-aligned UI-only fix.")


def prepare(rig: ExitRig) -> None:
    """Buggy checkout on main (pushed), coupon build agent, browser regression runner."""
    seed_app(rig.repo)
    git(rig.repo, "add", "-A")
    git(rig.repo, "commit", "-q", "-m", "coupon checkout (expired code bug)")
    git(rig.repo, "push", "-q", "origin", "main")
    agent = write_script(rig.root, "coupon_agent", build_agent_source())
    write_adapter(rig.home / ".maggy" / "adapters", fake_adapter_data(agent))
    profile_file = rig.home / ".maggy" / "harness.yaml"
    data = json.loads(profile_file.read_text())
    browsers = os.environ["PLAYWRIGHT_BROWSERS_PATH"]  # checks get a scrubbed env
    pytest = ["env", f"PLAYWRIGHT_BROWSERS_PATH={browsers}", sys.executable, "-m", "pytest"]
    data["commands"] = {"lint": STATIC}
    data["validation"].update(required=["lint"], check_timeout_s=300,
                              regression={"runner": "pytest", "command": shlex.join(pytest)})
    profile_file.write_text(json.dumps(data))


def run_once(rig: ExitRig) -> list[str]:
    done = rig.maggy("run", "--once", "--repo", str(rig.repo), "--awg-bin", str(rig.awg_bin))
    assert done.returncode == 0, done.stderr
    return done.stdout.strip().split("\t")


def verify_once(rig: ExitRig, fakes: tuple[list, FakeCouncil]) -> RunReport:
    """One in-process pass with fake vision backends and review council."""
    vision, council = fakes
    opts = RunCliOptions(once=True, project=None, adapter=None, repo=rig.repo, state_dir=None,
                         awg_bin=rig.awg_bin)
    runner = build_runner(opts)
    return Runner(runner.awg, replace(runner.config, vision=vision, council=council)).run_once()


def caps(rig: ExitRig, ref: str) -> list[str]:
    shown = dict(rig.awg("show", ref, "--json"))
    return list(shown["work"]["execution_policy"].get("capabilities") or [])


def approve_baselines(rig: ExitRig, ref: str) -> list[str]:
    """The human reviews each proposed image and records the sha256-bound DECISION."""
    notes = rig.awg("annotations", ref, "--json")
    proposals = [n for n in notes if annotation_key(n).startswith("baseline-proposed:")]
    keys = []
    for note in proposals:
        data = dict(note.get("data") or {})
        key = f"baseline-approved:{data['criterion_id']}:{data['viewport']}"
        rig.awg("decision", ref, "--key", key, "--title", "baseline approved",
                "--data", json.dumps({"sha256": data["sha256"]}), "--json")
        keys.append(key)
    rig.awg("state", ref, "READY", "--reason=baselines approved", "--json")
    return sorted(keys)

