"""Runner-side commit of the agent's changes and protected-path detection (RFC §2.6.2/5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.worker.commit import MAGGY_EMAIL, MAGGY_NAME, commit_candidate
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.protected import protected_paths
from maggy.worker.worktree import WorktreeError, create_attempt_worktree
from worker_git_helpers import FAKE_AGENT, fake_adapter, git, init_repo, profile, write_script


def _spec(tmp_path: Path, prompt: str = "edit") -> WorkerSpec:
    repo = tmp_path / "repo"
    repo.mkdir()
    base = init_repo(repo)
    return WorkerSpec(awg_ref="AWG-7", attempt_id="att-1", fencing_token="local", stage="build",
                      repo=repo, base_commit=base, spec_version=0,
                      workspace=tmp_path / "wt" / "AWG-7", permission="workspace",
                      deadline_s=30, budget_usd=0.5, prompt=prompt)


def _run(tmp_path: Path, prompt: str = "edit"):
    spec = _spec(tmp_path, prompt)
    create_attempt_worktree(spec)
    agent = write_script(tmp_path, "agent", FAKE_AGENT)
    attempt = Attempt(spec=spec, adapter=fake_adapter(agent), profile=profile(),
                      state_dir=tmp_path / "state")
    return spec, run_attempt(attempt)


def test_worktree_is_on_stable_branch_at_base(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    path = create_attempt_worktree(spec)
    assert path == spec.workspace
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD") == "maggy/AWG-7"
    assert git(path, "rev-parse", "HEAD") == spec.base_commit


def test_worktree_refuses_existing_branch(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    git(spec.repo, "branch", "maggy/AWG-7")
    with pytest.raises(WorktreeError, match="maggy/AWG-7"):
        create_attempt_worktree(spec)


def test_runner_commits_all_agent_changes_as_maggy(tmp_path: Path) -> None:
    spec, result = _run(tmp_path)
    sha = result.candidate_commit
    assert sha and sha != spec.base_commit
    assert git(spec.workspace, "status", "--porcelain") == ""
    assert git(spec.repo, "log", "-1", "--format=%an <%ae>|%cn <%ce>", sha) == (
        f"{MAGGY_NAME} <{MAGGY_EMAIL}>|{MAGGY_NAME} <{MAGGY_EMAIL}>")
    message = git(spec.repo, "log", "-1", "--format=%B", sha)
    assert "AWG-7" in message and "att-1" in message
    assert sorted(result.changed_files) == [".github/workflows/ci.yml", "README.md",
                                            "new_file.txt"]
    tree = git(spec.repo, "ls-tree", "-r", "--name-only", sha).splitlines()
    assert "new_file.txt" in tree and "build.log" not in tree


def test_protected_path_edit_blocks_for_human(tmp_path: Path) -> None:
    _, result = _run(tmp_path)
    assert result.outcome == "blocked"
    assert result.blocker is not None
    assert ".github/workflows/ci.yml" in result.blocker.question
    assert "WAITING_HUMAN" in result.blocker.question


def test_no_change_gives_no_candidate(tmp_path: Path) -> None:
    spec, result = _run(tmp_path, prompt="noop")
    assert result.outcome == "succeeded"
    assert result.candidate_commit is None and result.changed_files == []
    assert result.checks == [] and result.blocker is None
    assert result.agent == "fakeedit"


def test_commit_candidate_ignores_untouched_worktree(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    create_attempt_worktree(spec)
    assert commit_candidate(spec).commit is None


def test_protected_paths_cover_risk_ci_and_policy() -> None:
    changed = ["src/payments/charge.py", ".github/x.yml", ".maggy/harness.yaml", "src/ok.py"]
    assert protected_paths(changed, profile()) == changed[:3]
