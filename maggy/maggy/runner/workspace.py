"""The stable per-item worktree on branch maggy/<ref>, created or resumed (RFC §2.4)."""

from __future__ import annotations

import re
from pathlib import Path

from maggy.worker.git_ops import run_git
from maggy.worker.worktree import WorktreeError, attempt_branch

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def safe_name(value: str) -> str:
    """`value` if usable as a path component and branch suffix, else WorktreeError."""
    if not SAFE_NAME.match(value):
        raise WorktreeError(f"refusing unsafe name {value!r} for a branch or path")
    return value


def prepare_workspace(repo: Path, workspace: Path, ref: str) -> str:
    """Ensure `workspace` is a worktree on maggy/<ref>; returns the base commit to diff from.

    An existing branch is resumed (never reset) so an interrupted attempt's work survives.
    """
    branch = attempt_branch(safe_name(ref))
    head = run_git(repo, ["rev-parse", "HEAD"])
    if _registered(repo, workspace):
        return run_git(repo, ["merge-base", head, branch])
    if workspace.exists():
        raise WorktreeError(f"{workspace} exists but is not a worktree of {repo}")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if run_git(repo, ["branch", "--list", branch]):
        run_git(repo, ["worktree", "add", "-q", str(workspace), branch])
        return run_git(repo, ["merge-base", head, branch])
    run_git(repo, ["worktree", "add", "-q", "-b", branch, str(workspace), head])
    return head


def _registered(repo: Path, workspace: Path) -> bool:
    listing = run_git(repo, ["worktree", "list", "--porcelain"]).splitlines()
    target = workspace.resolve()
    paths = [Path(line.removeprefix("worktree ")) for line in listing
             if line.startswith("worktree ")]
    return any(path.resolve() == target for path in paths)
