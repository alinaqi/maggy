"""The replay set: 5 self-contained tasks with fixture repos and hidden acceptance checks."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest

from maggy.worker.blocker import BLOCKER_INSTRUCTIONS
from maggy.worker.parsers import RawRun, parse_run
from maggy.worker.replay.fake import RECORDINGS, fake_stdout
from maggy.worker.replay.tasks import (check_commands, load_tasks, materialize, replay_prompt,
                                       write_accept)
from worker_fixture_helpers import FIXTURES
from worker_git_helpers import git

IDS = ["implement", "off_by_one", "cli_flag", "refactor", "ambiguous"]
PASS_IDS = IDS[:4]
PARSERS = {"claude": "claude-json", "codex": "codex-jsonl", "opencode": "opencode-json",
           "pi": "pi-jsonl"}
FIXTURE_FILES = {"claude": "success.json", "codex": "success.jsonl",
                 "opencode": "success.jsonl", "pi": "success.jsonl"}


def _checks_pass(repo: Path, accept: Path) -> dict[str, bool]:
    commands = check_commands(accept)
    return {name: subprocess.run(shlex.split(line), cwd=repo, capture_output=True,
                                 check=False).returncode == 0
            for name, line in commands.items()}


def test_replay_set_has_five_tasks_covering_each_kind() -> None:
    tasks = load_tasks()
    assert [task.id for task in tasks] == IDS
    assert [task.expect for task in tasks] == ["pass"] * 4 + ["blocker"]
    assert [task.id for task in load_tasks(["ambiguous", "implement"])] == ["ambiguous",
                                                                           "implement"]


def test_unknown_task_is_an_error() -> None:
    with pytest.raises(KeyError, match="nope"):
        load_tasks(["nope"])


def test_fixture_repo_is_a_clean_committed_git_repo(tmp_path: Path) -> None:
    [task] = load_tasks(["implement"])
    repo = materialize(task, tmp_path / "repo")
    assert git(repo, "status", "--porcelain") == ""
    assert sorted(git(repo, "ls-files").splitlines()) == [".gitignore", "test_textutil.py",
                                                          "textutil.py"]
    assert "__pycache__/" in (repo / ".gitignore").read_text()


@pytest.mark.parametrize("task_id", PASS_IDS)
def test_acceptance_fails_at_base_and_passes_with_reference_solution(tmp_path: Path,
                                                                     task_id: str) -> None:
    [task] = load_tasks([task_id])
    repo, accept = materialize(task, tmp_path / "repo"), write_accept(task, tmp_path / "acc")
    assert _checks_pass(repo, accept)["e2e"] is False
    for rel, text in task.solution.items():
        (repo / rel).write_text(text)
    assert _checks_pass(repo, accept) == {"test": True, "e2e": True}


def test_ambiguous_task_expects_a_question() -> None:
    [task] = load_tasks(["ambiguous"])
    assert task.solution == {} and task.fake_reply.startswith("QUESTION:")
    assert BLOCKER_INSTRUCTIONS in replay_prompt(task)
    assert replay_prompt(task).startswith(task.prompt.strip())


@pytest.mark.parametrize("agent", sorted(PARSERS))
def test_recordings_are_the_recorded_fixtures(agent: str) -> None:
    recorded = (FIXTURES / agent / FIXTURE_FILES[agent]).read_text()
    assert (RECORDINGS / Path(FIXTURE_FILES[agent]).with_stem(agent).name).read_text() == recorded


@pytest.mark.parametrize("agent", sorted(PARSERS))
def test_fake_stdout_carries_the_task_reply(agent: str) -> None:
    reply = 'QUESTION: Which "rules"?'
    parsed = parse_run(PARSERS[agent], RawRun(stdout=fake_stdout(agent, reply)), [])
    assert parsed.final_text == reply and parsed.error is None
