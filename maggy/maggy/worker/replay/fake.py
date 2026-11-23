"""Offline fake agent CLIs replaying recorded output (`maggy worker replay` without --live).

`write_fake_bin` puts one executable per agent name (claude, codex, opencode, pi) in a bin
dir that the pipeline prepends to the worker's PATH. Run through the shipped adapter argv,
the fake logs its argv, applies the task's reference solution in its cwd and prints that
agent's recorded output with the final text replaced by the task's reply.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import yaml

from maggy.worker.replay.tasks import ReplayTask

RECORDINGS = Path(__file__).parent / "recordings"
AGENT_SCRIPT = """\
import json, sys
from pathlib import Path
here = Path(__file__).parent
plan = json.loads((here / "plan.json").read_text())
with (here / "calls.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[2:]) + "\\n")
for rel, text in plan["files"].items():
    Path(rel).parent.mkdir(parents=True, exist_ok=True)
    Path(rel).write_text(text)
sys.stdout.write(plan["stdout"][sys.argv[1]])
"""


def recordings() -> dict[str, Path]:
    meta = yaml.safe_load((RECORDINGS / "meta.yaml").read_text())
    return {agent: RECORDINGS / entry["file"] for agent, entry in meta.items()}


def fake_stdout(agent: str, reply: str) -> str:
    """The agent's recording with the JSON string "done" (its final text) set to `reply`."""
    return recordings()[agent].read_text().replace('"done"', json.dumps(reply))


def write_fake_bin(task: ReplayTask, dest: Path) -> Path:
    """A bin dir with a fake CLI for every recorded agent, scripted for `task`."""
    dest.mkdir(parents=True, exist_ok=True)
    stdout = {agent: fake_stdout(agent, task.fake_reply) for agent in recordings()}
    plan = {"files": task.solution, "stdout": stdout}
    (dest / "plan.json").write_text(json.dumps(plan))
    script = dest / "fake_agent.py"
    script.write_text(AGENT_SCRIPT)
    for agent in stdout:
        _wrapper(dest / agent, script, agent)
    return dest


def _wrapper(path: Path, script: Path, agent: str) -> None:
    run = shlex.join([sys.executable, str(script), agent])
    path.write_text(f'#!/bin/sh\nexec {run} "$@"\n')
    path.chmod(0o755)
