"""Decide whether an isolated executor workspace may be deleted.

A workspace is only safe to delete once its changes reached the repo.
Otherwise its path is recorded on the session so the work can be recovered.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_workspace(session: dict, repo_dir: Path, ws_dir: Path) -> bool:
    """Merge a completed session's workspace. True means safe to delete."""
    if session.get("status") == "completed" and _merge(repo_dir, ws_dir):
        return True
    if session.get("status") == "completed":
        session["status"] = "merge_failed"
        session["error"] = f"Merge failed; work kept in {ws_dir}"
    session["preserved_workspace"] = str(ws_dir)
    logger.warning("Keeping unmerged workspace %s", ws_dir)
    return False


def _merge(repo_dir: Path, ws_dir: Path) -> bool:
    """Run merge_changes, treating any exception as a failed merge."""
    from maggy.orchestrator import merge
    try:
        return bool(merge.merge_changes(repo_dir, ws_dir))
    except Exception:
        logger.exception("Merge from %s raised", ws_dir)
        return False
