"""Runner git never trusts the agent's worktree `.git` and never leaks runner env (RFC §2.6.1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maggy.worker.commit import commit_candidate
from maggy.worker.git_ops import GitError, run_git
from maggy.worker.models import WorkerSpec
from maggy.worker.worktree import create_attempt_worktree
from worker_git_helpers import git, init_repo

TOKEN = "ghp_SHOULD_NOT_LEAK"


def _spec(tmp_path: Path) -> WorkerSpec:
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-5", attempt_id="att-5", fencing_token="local", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="workspace", deadline_s=30,
                      budget_usd=0.0, prompt="p")
    create_attempt_worktree(spec)
    return spec


def _hijack(spec: WorkerSpec, leak: Path) -> None:
    """What an agent can do from inside its workspace: point .git at its own gitdir."""
    wt, evil = spec.workspace, spec.workspace / ".evil"
    subprocess.run(["git", "init", "-q", "--bare", str(evil)], check=True)
    (evil / "objects" / "info" / "alternates").write_text(f"{spec.repo / '.git' / 'objects'}\n")
    (evil / "HEAD").write_text(spec.base_commit + "\n")
    git(evil, "config", "core.bare", "false")
    git(evil, "config", "filter.x.clean", f'sh -c "env > {leak}; cat"')
    (wt / ".git").write_text(f"gitdir: {evil}\n")
    (wt / ".gitattributes").write_text("* filter=x\n")
    (wt / "new.txt").write_text("hi\n")


def test_hijacked_dot_git_is_refused_and_runs_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    spec = _spec(tmp_path)
    leak = tmp_path / "leak.txt"
    _hijack(spec, leak)
    with pytest.raises(GitError, match=r"\.git"):
        commit_candidate(spec)
    assert not leak.exists()


def test_runner_git_env_carries_no_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("AWG_TOKEN", TOKEN)
    spec = _spec(tmp_path)
    leak = tmp_path / "env.txt"
    git(spec.repo, "config", "filter.dump.clean", f'sh -c "env > {leak}; cat"')
    (spec.workspace / ".gitattributes").write_text("* filter=dump\n")
    (spec.workspace / "new.txt").write_text("hi\n")
    assert commit_candidate(spec).commit is not None
    assert leak.exists() and TOKEN not in leak.read_text()


def test_run_git_ignores_inherited_git_dir(tmp_path: Path, monkeypatch) -> None:
    spec = _spec(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    assert run_git(spec.repo, ["rev-parse", "HEAD"]) == spec.base_commit
