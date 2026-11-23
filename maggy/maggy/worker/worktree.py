"""Per-attempt and per-check git worktrees (RFC §2.3 isolation, §2.6.2)."""

from __future__ import annotations

from pathlib import Path

from maggy.worker.git_ops import GitError, run_git
from maggy.worker.models import WorkerSpec


class WorktreeError(GitError):
    """The attempt worktree could not be created safely."""


def attempt_branch(awg_ref: str) -> str:
    return f"maggy/{awg_ref}"


def create_attempt_worktree(spec: WorkerSpec) -> Path:
    """New worktree at `spec.workspace` on branch maggy/<awg_ref>, from `spec.base_commit`.

    An existing branch is refused rather than reset, so no earlier attempt's work is lost.
    """
    branch = attempt_branch(spec.awg_ref)
    run_git(spec.repo, ["check-ref-format", "--branch", branch])
    if run_git(spec.repo, ["branch", "--list", branch]):
        raise WorktreeError(f"branch {branch} already exists; resume or delete it first")
    spec.workspace.parent.mkdir(parents=True, exist_ok=True)
    run_git(spec.repo, ["worktree", "add", "-q", "-b", branch, str(spec.workspace),
                        spec.base_commit])
    return spec.workspace


def add_detached(repo: Path, sha: str, dest: Path) -> Path:
    """A fresh detached worktree at `sha` (for checks)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_git(repo, ["worktree", "add", "-q", "--detach", str(dest), sha])
    return dest


def remove_worktree(repo: Path, path: Path) -> None:
    run_git(repo, ["worktree", "remove", "--force", str(path)])
