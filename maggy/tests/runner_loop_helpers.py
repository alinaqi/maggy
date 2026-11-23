"""A throwaway repo, fake agent CLIs and a FakeAwg wired into a Runner (runner loop tests)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.awg_errors import FenceStale
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from maggy.runner.config import project_capability
from maggy.runner.loop import Runner, RunnerConfig
from worker_git_helpers import DUMP_CHECK, dump_command, fake_adapter, init_repo, profile, \
    write_script

CAPS = ["maggy-runner", "stage:build"]

EDIT_AGENT = """
from pathlib import Path
Path("feature.txt").write_text("done\\n")
"""

QUESTION_AGENT = """
print("I cannot tell which database to use.")
print("QUESTION: Should sessions live in Postgres or Redis?")
"""

PROTECTED_AGENT = """
from pathlib import Path
Path("src/payments").mkdir(parents=True, exist_ok=True)
Path("src/payments/charge.py").write_text("x = 1\\n")
"""

# Sleeps, then writes a marker: a killed worker never writes it.
SLEEPY_AGENT = """
import time
from pathlib import Path
time.sleep(20)
Path("late.txt").write_text("should never exist\\n")
"""


class StealingAwg(FakeAwg):
    """Another runner reclaims the item after the first (pre-worktree) fence check."""

    beats = 0

    def heartbeat(self, claim: Claim) -> Claim:
        self.beats += 1
        if self.beats == 1:
            return super().heartbeat(claim)
        self.items[claim.ref].fencing_token += 1
        raise FenceStale("stale_fencing_token", "fencing token is not the live lease")


@dataclass
class Rig:
    runner: Runner
    awg: FakeAwg
    ref: str
    repo: Path
    state: Path
    check_out: Path


def make_rig(tmp_path: Path, agent: str, **options) -> Rig:
    """`options`: awg, heartbeat_s, project, pr_step, capabilities (default: CAPS bound to
    the project), attributes, check_exit, state_file."""
    awg = options.get("awg") or FakeAwg(lease_seconds=900)
    tagged = [*CAPS, project_capability(options.get("project", "demo"))]
    ref = awg.add_item("Add feature", capabilities=options.get("capabilities", tagged),
                       acceptance_criteria=["feature.txt exists"])
    awg.items[ref].attributes.update(options.get("attributes", {}))
    repo, state = tmp_path / "repo", tmp_path / "state"
    repo.mkdir()
    init_repo(repo)
    config = _config(tmp_path, agent, options)
    return Rig(Runner(awg, config), awg, ref, repo, state, tmp_path / "check.json")


def _config(tmp_path: Path, agent: str, options: dict) -> RunnerConfig:
    check = dump_command(write_script(tmp_path, "dump", DUMP_CHECK), tmp_path / "check.json",
                         options.get("check_exit", 0))
    return RunnerConfig(repo=tmp_path / "repo", state_dir=tmp_path / "state",
                        adapter=fake_adapter(write_script(tmp_path, "agent", agent)),
                        profile=profile(commands={"test": check}, required=["test"]),
                        project=options.get("project", "demo"),
                        heartbeat_s=options.get("heartbeat_s", 30.0),
                        pr_step=options.get("pr_step"), state_file=options.get("state_file"))


def decisions(rig: Rig) -> list[str]:
    """Every decision event the runner logged for its attempts."""
    logs = sorted((rig.state / "attempts").glob("*/runner.jsonl"))
    return [json.loads(line)["event"] for log in logs for line in log.read_text().splitlines()]
