"""Merge changes from isolated workspace back to original repo.

The patch covers everything since the workspace's base commit (the
merge-base with the repo's HEAD): every commit, plus uncommitted and
untracked (non-ignored) files. Any git failure reports False so callers
keep the workspace instead of deleting unmerged work. False also means the
repo is untouched: a conflicting 3-way apply is rolled back (see merge_rollback).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from . import merge_rollback

logger = logging.getLogger(__name__)


class MergeError(RuntimeError):
    """A git step needed to build or apply the patch failed."""


def merge_changes(repo_dir: Path, ws_dir: Path) -> bool:
    """Apply all workspace changes to repo. True only when nothing is lost."""
    try:
        patch = _generate_patch(repo_dir, ws_dir)
    except (MergeError, OSError) as exc:
        logger.warning("Cannot build patch from %s: %s", ws_dir, exc)
        return False
    if not patch:
        logger.info("No changes to merge from %s", ws_dir)
        return True
    return _apply_patch(repo_dir, patch)


def _generate_patch(repo_dir: Path, ws_dir: Path) -> bytes:
    """Diff the workspace (index incl. untracked) against its base commit.

    No rename detection: a rename is a delete plus an add, so every path the
    patch touches is listed by ``git apply --numstat`` for rollback.
    """
    head = _git_ok(["-C", str(repo_dir), "rev-parse", "HEAD"]).strip()
    base = _git_ok(["-C", str(ws_dir), "merge-base", "HEAD", head.decode()])
    _git_ok(["-C", str(ws_dir), "add", "-A"])
    return _git_ok([
        "-C", str(ws_dir), "diff", "--cached", "--binary", "--no-renames",
        base.strip().decode(),
    ])


def _apply_patch(repo_dir: Path, patch: bytes) -> bool:
    """Apply patch with 3-way merge; on failure restore the repo and say False."""
    try:
        paths = merge_rollback.touched_paths(repo_dir, patch)
        snap = merge_rollback.take_snapshot(repo_dir, paths)
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("Cannot snapshot repo before merge: %s", exc)
        return False
    result = _run_git(
        ["git", "-C", str(repo_dir), "apply", "--3way", "-"],
        input_data=patch,
    )
    if result.returncode != 0:
        logger.warning("Patch apply failed, rolling back: %s", result.stderr)
        merge_rollback.restore(snap)
        return False
    return True


def _git_ok(args: list[str]) -> bytes:
    """Run git; raise MergeError on a non-zero exit."""
    result = _run_git(["git", *args])
    if result.returncode != 0:
        raise MergeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def _run_git(
    cmd: list[str], input_data: bytes | None = None,
) -> subprocess.CompletedProcess:
    """Run a git command with optional stdin."""
    return subprocess.run(
        cmd, capture_output=True, check=False,
        input=input_data,
    )
