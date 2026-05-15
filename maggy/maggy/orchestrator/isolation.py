"""Isolation strategy resolver and workspace provisioning."""
from __future__ import annotations

import logging
import shutil
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class IsolationLevel(Enum):
    """Workspace isolation strategies."""

    CONTAINER = "container"
    WORKTREE = "worktree"
    LOCK_ONLY = "lock_only"


def detect_capabilities() -> IsolationLevel:
    """Detect best available isolation level."""
    if shutil.which("docker"):
        return IsolationLevel.CONTAINER
    if shutil.which("git"):
        return IsolationLevel.WORKTREE
    return IsolationLevel.LOCK_ONLY


def provision_workspace(
    level: IsolationLevel,
    repo_dir: Path,
    session_id: str,
    base_dir: Path,
) -> str:
    """Provision an isolated workspace at the given level."""
    if level == IsolationLevel.WORKTREE:
        return _provision_worktree(repo_dir, session_id, base_dir)
    if level == IsolationLevel.CONTAINER:
        return _provision_worktree(repo_dir, session_id, base_dir)
    return str(repo_dir)


def cleanup_workspace(
    level: IsolationLevel, repo_dir: Path, ws_path: str,
) -> None:
    """Clean up an isolated workspace."""
    if level == IsolationLevel.WORKTREE:
        from maggy.orchestrator.worktree import remove_worktree
        remove_worktree(repo_dir, Path(ws_path))
    elif level == IsolationLevel.CONTAINER:
        from maggy.orchestrator.worktree import remove_worktree
        remove_worktree(repo_dir, Path(ws_path))


def _provision_worktree(
    repo_dir: Path, session_id: str, base_dir: Path,
) -> str:
    """Create a git worktree for session isolation."""
    from maggy.orchestrator.worktree import create_worktree
    wt = create_worktree(repo_dir, session_id, base_dir)
    logger.info("Provisioned worktree %s for %s", wt, session_id)
    return str(wt)
