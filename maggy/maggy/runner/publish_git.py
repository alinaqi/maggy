"""Stable-branch push for the runner: only refs/heads/maggy/<ref>, always with a lease.

Argv only, through Phase 2's hardened `run_git` (no hooks, scrubbed env). Maggy injects no
credentials: the push authenticates with the user's own git config (and ssh agent socket).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from maggy.runner.workspace import safe_name
from maggy.worker.git_ops import GitError, run_git
from maggy.worker.worktree import attempt_branch

MAGGY_BRANCH = re.compile(r"^maggy/[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


class PublishError(RuntimeError):
    """A push or PR action was refused or failed; nothing further is published."""


def branch_for(ref: str) -> str:
    """maggy/<ref> for a safe AWG ref (WorktreeError otherwise)."""
    return attempt_branch(safe_name(ref))


def checked(branch: str) -> str:
    """`branch` if it is a maggy/<ref> branch, else PublishError (RFC §2.6.5)."""
    if not MAGGY_BRANCH.match(branch) or ".." in branch:
        raise PublishError(f"refusing to publish {branch!r}: only maggy/<ref> branches")
    return branch


def remote_sha(repo: Path, branch: str) -> str:
    """The SHA of origin's refs/heads/<branch>, or "" when it does not exist."""
    listing = run_git(repo, ["ls-remote", "origin", f"refs/heads/{checked(branch)}"])
    return listing.split("\t")[0] if listing else ""


def push_branch(repo: Path, branch: str, shas: tuple[str, str]) -> None:
    """Push `sha` to origin's maggy branch only if it is still at `expected` ("" = absent)."""
    sha, expected = shas
    target = f"refs/heads/{checked(branch)}"
    lease = f"--force-with-lease={target}:{expected}"
    try:
        run_git(repo, ["push", "--porcelain", lease, "origin", f"{sha}:{target}"], _ssh_agent())
    except GitError as exc:
        raise PublishError(f"push of {branch} rejected: {exc}") from exc


def default_base(repo: Path) -> str:
    """origin's default branch (refs/remotes/origin/HEAD), else "main"."""
    try:
        head = run_git(repo, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    except GitError:
        return "main"
    return head.removeprefix("origin/") or "main"


def _ssh_agent() -> dict[str, str]:
    sock = os.environ.get("SSH_AUTH_SOCK")
    return {"SSH_AUTH_SOCK": sock} if sock else {}
