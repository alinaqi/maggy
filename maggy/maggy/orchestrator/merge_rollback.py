"""Snapshot the paths a patch touches so a failed ``git apply`` can be undone.

``git apply --3way`` writes conflict markers and unmerged index entries before it
reports failure. Restoring the index file and every touched path makes a failed
merge leave the repo exactly as it was.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Saved:
    """A regular file's bytes and mode, or a symlink's target (``link``)."""

    data: bytes = b""
    mode: int = 0
    link: str | None = None


@dataclass
class Snapshot:
    repo_dir: Path
    index: bytes | None
    files: dict[str, Saved | None] = field(default_factory=dict)


def touched_paths(repo_dir: Path, patch: bytes) -> list[str]:
    """Every path the patch reads or writes."""
    out = subprocess.run(
        ["git", "-C", str(repo_dir), "apply", "--numstat", "-z", "-"],
        input=patch, capture_output=True, check=True,
    ).stdout.decode(errors="surrogateescape")
    return _parse_numstat_z(out)


def _parse_numstat_z(out: str) -> list[str]:
    """``A\tD\tpath`` entries (patches are built with ``--no-renames``)."""
    return [t.split("\t", 2)[2] for t in out.split("\0") if t.count("\t") >= 2]


def take_snapshot(repo_dir: Path, paths: list[str]) -> Snapshot:
    """Record the index file plus the bytes and mode (or absence) of each path."""
    index = _index_path(repo_dir)
    snap = Snapshot(repo_dir, index.read_bytes() if index.exists() else None)
    for rel in paths:
        target = repo_dir / rel
        if target.is_dir() and not target.is_symlink():
            continue  # merge patches write files and symlinks, never directories
        snap.files[rel] = _saved(target)
    return snap


def _saved(target: Path) -> Saved | None:
    if target.is_symlink():
        return Saved(link=os.readlink(target))
    if not target.exists():
        return None
    return Saved(target.read_bytes(), target.stat().st_mode)


def restore(snap: Snapshot) -> None:
    """Put the index and every snapshotted path back as it was."""
    index = _index_path(snap.repo_dir)
    if snap.index is not None:
        index.write_bytes(snap.index)
    for rel, saved in snap.files.items():
        _restore_path(snap.repo_dir / rel, saved)


def _restore_path(target: Path, saved: Saved | None) -> None:
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    elif target.exists() or target.is_symlink():
        target.unlink()
    if saved is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if saved.link is not None:
        os.symlink(saved.link, target)
        return
    target.write_bytes(saved.data)
    os.chmod(target, saved.mode)


def _index_path(repo_dir: Path) -> Path:
    out = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--git-path", "index"],
        capture_output=True, check=True, text=True,
    ).stdout.strip()
    path = Path(out)
    return path if path.is_absolute() else repo_dir / path
