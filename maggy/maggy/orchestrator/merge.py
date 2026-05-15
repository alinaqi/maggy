"""Merge changes from isolated workspace back to original repo."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_changes(repo_dir: Path, ws_dir: Path) -> bool:
    """Generate patch from workspace and apply to repo."""
    patch = _generate_patch(ws_dir)
    if not patch:
        logger.info("No changes to merge from %s", ws_dir)
        return True
    return _apply_patch(repo_dir, patch)


def _generate_patch(ws_dir: Path) -> bytes:
    """Generate a diff of all changes in workspace."""
    result = _run_git([
        "git", "-C", str(ws_dir),
        "diff", "HEAD@{1}..HEAD",
    ])
    return result.stdout


def _apply_patch(repo_dir: Path, patch: bytes) -> bool:
    """Apply patch to repo with 3-way merge."""
    result = _run_git(
        [
            "git", "-C", str(repo_dir),
            "apply", "--3way", "-",
        ],
        input_data=patch,
    )
    if result.returncode != 0:
        logger.warning("Patch apply failed: %s", result.stderr)
        return False
    return True


def _run_git(
    cmd: list[str], input_data: bytes | None = None,
) -> subprocess.CompletedProcess:
    """Run a git command with optional stdin."""
    return subprocess.run(
        cmd, capture_output=True, check=False,
        input=input_data,
    )
