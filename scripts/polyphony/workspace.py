"""Workspace manager — per-task git clone lifecycle (spec §6).

Each task+attempt gets an isolated directory with a full git clone.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def workspace_path(
    base_dir: Path,
    task_id: str,
    attempt: int,
) -> Path:
    """Build workspace directory path, sanitizing task_id."""
    safe_id = re.sub(r"[^\w\-.]", "_", task_id)
    return base_dir / safe_id / str(attempt)


def create_workspace(
    base_dir: Path,
    task_id: str,
    attempt: int,
    repo_url: str,
    ref: str,
    mirror_path: Path | None = None,
) -> Path:
    """Clone repo into workspace and checkout ref."""
    ws = workspace_path(base_dir, task_id, attempt)
    ws.mkdir(parents=True, exist_ok=True)

    clone_cmd = ["git", "clone"]
    if mirror_path and mirror_path.exists():
        clone_cmd += [
            "--reference", str(mirror_path),
            "--dissociate",
        ]
    clone_cmd += [repo_url, str(ws)]
    _run_git(clone_cmd)

    checkout_cmd = ["git", "-C", str(ws), "checkout", ref]
    _run_git(checkout_cmd)

    return ws


def cleanup_workspace(ws_path: Path) -> None:
    """Remove workspace directory. No error if missing."""
    if ws_path.exists():
        shutil.rmtree(ws_path)


def list_workspaces(base_dir: Path) -> list[Path]:
    """List all workspace directories under base_dir."""
    if not base_dir.exists():
        return []
    result: list[Path] = []
    for task_dir in sorted(base_dir.iterdir()):
        if task_dir.is_dir():
            for attempt_dir in sorted(task_dir.iterdir()):
                if attempt_dir.is_dir():
                    result.append(attempt_dir)
    return result


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a git command. Thin wrapper for mocking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
