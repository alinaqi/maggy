"""The replay set: tiny fixture repos, prompts and hidden acceptance checks (Phase 2 exit).

Each `tasks/*.yaml` holds one task: the repo `files` (git-initialised at runtime in a temp
dir), the `prompt`, `accept` tests kept outside the repo (so an agent cannot weaken them),
a reference `solution` the offline fake agents apply, and the `expect`ed outcome.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Literal

import yaml

from maggy.harness.schema_sections import Strict
from maggy.worker.blocker import BLOCKER_INSTRUCTIONS
from maggy.worker.commit import IDENTITY
from maggy.worker.git_ops import run_git

TASKS_DIR = Path(__file__).parent / "tasks"
GITIGNORE = "__pycache__/\n*.pyc\n"


class ReplayTask(Strict):
    id: str
    title: str
    expect: Literal["pass", "blocker"]
    prompt: str
    files: dict[str, str]
    accept: dict[str, str]
    solution: dict[str, str] = {}
    fake_reply: str = "done"


def load_tasks(ids: list[str] | None = None) -> list[ReplayTask]:
    """All tasks in file order, or the named ones in the given order (KeyError if unknown)."""
    tasks = [ReplayTask.model_validate(yaml.safe_load(path.read_text()))
             for path in sorted(TASKS_DIR.glob("*.yaml"))]
    if ids is None:
        return tasks
    by_id = {task.id: task for task in tasks}
    unknown = [name for name in ids if name not in by_id]
    if unknown:
        raise KeyError(f"unknown replay task(s): {', '.join(unknown)}; "
                       f"expected some of {', '.join(by_id)}")
    return [by_id[name] for name in ids]


def _write(files: dict[str, str], dest: Path) -> Path:
    for rel, text in files.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return dest


def materialize(task: ReplayTask, dest: Path) -> Path:
    """The task's fixture repo at `dest`: files plus .gitignore, committed on `main`."""
    repo = _write({**task.files, ".gitignore": GITIGNORE}, dest)
    run_git(repo, ["init", "-q", "-b", "main"])
    run_git(repo, ["add", "-A"])
    run_git(repo, ["commit", "-q", "-m", f"replay fixture: {task.id}"], IDENTITY)
    return repo


def write_accept(task: ReplayTask, dest: Path) -> Path:
    """The hidden acceptance tests, written outside the repo."""
    return _write(task.accept, dest)


def check_commands(accept: Path) -> dict[str, str]:
    """`test`: the repo's own unittest suite; `e2e`: the hidden acceptance tests."""
    python = sys.executable
    unit = [python, "-m", "unittest", "discover", "-q"]
    hidden = [*unit, "-s", str(accept), "-t", str(accept), "-p", "accept_*.py"]
    return {"test": shlex.join(unit), "e2e": shlex.join(hidden)}


def replay_prompt(task: ReplayTask) -> str:
    return f"{task.prompt.strip()}\n\n{BLOCKER_INSTRUCTIONS}"
