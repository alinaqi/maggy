"""Runner-side changes to the item's maggy/<ref> branch (RFC §2.6.5: maggy/* only).

Each change is made in a fresh detached worktree at the branch head (never in a directory an
agent wrote to), committed as Maggy, then the branch is moved with a compare-and-swap
`update-ref`, so a concurrent move makes the change fail instead of being overwritten.
`integrate` merges the build children's branches (the integrated candidate);
`commit_files` adds approved baselines.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from maggy.runner.publish_git import branch_for
from maggy.worker.commit import IDENTITY
from maggy.worker.git_ops import GitError, run_git
from maggy.worker.worktree import add_detached, remove_worktree

Change = Callable[[Path], None]


def branch_head(repo: Path, ref: str) -> str | None:
    try:
        return run_git(repo, ["rev-parse", "--verify", "-q", f"refs/heads/{branch_for(ref)}"])
    except GitError:
        return None


def integrate(repo: Path, ref: str, children: list[str]) -> str:
    """maggy/<ref> with every existing maggy/<child> branch merged in (in plan order)."""
    branches = [branch_for(c) for c in children if branch_head(repo, c)]

    def merge(checkout: Path) -> None:
        for branch in branches:
            try:
                run_git(checkout, ["merge", "--no-ff", "--no-edit", "-m",
                                   f"maggy: integrate {branch}", f"refs/heads/{branch}"], IDENTITY)
            except GitError as exc:
                raise GitError(f"cannot integrate {branch} into {branch_for(ref)}: {exc}") from exc

    return _on_branch(repo, ref, merge)


def commit_files(repo: Path, ref: str, files: dict[str, Path]) -> str:
    """maggy/<ref> with `files` (repo path -> source) committed; unchanged when identical."""

    def write(checkout: Path) -> None:
        for name, source in files.items():
            target = checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        run_git(checkout, ["add", "--", *files])
        if run_git(checkout, ["status", "--porcelain", "--untracked-files=no"]):
            run_git(checkout, ["commit", "-q", "--no-verify", "-m",
                               f"maggy: approved baselines for {ref}"], IDENTITY)

    return _on_branch(repo, ref, write)


def _on_branch(repo: Path, ref: str, change: Change) -> str:
    old = branch_head(repo, ref)
    start = old or run_git(repo, ["rev-parse", "HEAD"])
    with tempfile.TemporaryDirectory(prefix="maggy-branch-") as scratch:
        checkout = add_detached(repo, start, Path(scratch) / "checkout")
        try:
            change(checkout)
            new = run_git(checkout, ["rev-parse", "HEAD"])
        finally:
            remove_worktree(repo, checkout)
    if new != old:
        run_git(repo, ["update-ref", "-m", "maggy verify", f"refs/heads/{branch_for(ref)}",
                       new, old or ""])
    return new
