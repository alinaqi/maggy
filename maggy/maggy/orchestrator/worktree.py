"""Git worktree lifecycle manager for session isolation."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def worktree_path(base_dir: Path, session_id: str) -> Path:
    """Build worktree path, sanitizing session_id."""
    safe_id = re.sub(r"[^\w\-.]", "_", session_id)
    return base_dir / "worktrees" / safe_id


def create_worktree(
    repo_dir: Path, session_id: str, base_dir: Path,
) -> Path:
    """Create a git worktree with a maggy branch."""
    wt = worktree_path(base_dir, session_id)
    wt.parent.mkdir(parents=True, exist_ok=True)
    branch = f"maggy/{session_id}"
    _run_git([
        "git", "-C", str(repo_dir),
        "worktree", "add",
        "-b", branch, str(wt),
    ])
    return wt


def remove_worktree(repo_dir: Path, wt_path: Path) -> None:
    """Remove a git worktree and prune."""
    _run_git([
        "git", "-C", str(repo_dir),
        "worktree", "remove", "--force", str(wt_path),
    ])


def list_worktrees(repo_dir: Path) -> list[str]:
    """List non-main worktree paths from porcelain output."""
    result = _run_git([
        "git", "-C", str(repo_dir),
        "worktree", "list", "--porcelain",
    ])
    paths: list[str] = []
    main_seen = False
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            path = line[len("worktree "):]
            if not main_seen:
                main_seen = True
                continue
            paths.append(path)
    return paths


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a git command. Thin wrapper for mocking."""
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False,
    )
