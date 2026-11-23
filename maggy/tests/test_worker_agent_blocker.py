"""Agent-raised blockers: a `QUESTION:` line in the final text blocks the attempt."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.worker.blocker import BLOCKER_INSTRUCTIONS, agent_blocker
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.worktree import create_attempt_worktree
from worker_git_helpers import fake_adapter, init_repo, profile, write_script

SAY = "import sys\nprint(sys.argv[-1])\n"


@pytest.mark.parametrize("text", ["QUESTION: Which rules apply?",
                                  "I can't tell.\n**QUESTION:** Which rules apply?",
                                  "question: Which rules apply?"])
def test_question_line_becomes_a_blocker(text: str) -> None:
    blocker = agent_blocker(text)
    assert blocker is not None and blocker.question == "Which rules apply?"


@pytest.mark.parametrize("text", ["done", "", "The QUESTION: is inline", "QUESTION:   "])
def test_no_question_line_means_no_blocker(text: str) -> None:
    assert agent_blocker(text) is None


def test_instructions_name_the_marker() -> None:
    assert "QUESTION:" in BLOCKER_INSTRUCTIONS


def _run(tmp_path: Path, prompt: str):
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-5", attempt_id="att-5", fencing_token="t", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="read_only", deadline_s=30,
                      budget_usd=0.1, prompt=prompt)
    create_attempt_worktree(spec)
    agent = fake_adapter(write_script(tmp_path, "say", SAY))
    return run_attempt(Attempt(spec=spec, adapter=agent, profile=profile(),
                               state_dir=tmp_path / "state"))


def test_pipeline_reports_agent_question_as_blocked(tmp_path: Path) -> None:
    result = _run(tmp_path, "QUESTION: Which discount rules?")
    assert result.outcome == "blocked"
    assert result.blocker is not None and result.blocker.question == "Which discount rules?"


def test_pipeline_plain_answer_succeeds(tmp_path: Path) -> None:
    result = _run(tmp_path, "done")
    assert (result.outcome, result.blocker) == ("succeeded", None)
