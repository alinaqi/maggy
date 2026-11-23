"""Filesystem helpers for apply: root containment, atomic writes, backups."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path


def real(path: Path) -> Path:
    return Path(os.path.realpath(path))


def inside_root(path: Path, root: Path) -> bool:
    """True when `path`, with every symlink resolved, stays inside `root`."""
    return real(path).is_relative_to(real(root))


def read_text(path: Path) -> str | None:
    """Exact file text (no newline translation), or None when absent."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def target_mode(path: Path, references_token: bool) -> int:
    """0600 for files pointing at token files, else keep the current mode."""
    if references_token:
        return 0o600
    return stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644


def atomic_write(path: Path, text: str, mode: int) -> None:
    """Write via a temp file in the same directory, then rename over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def backup_file(path: Path, root: Path, backup_dir: Path) -> Path:
    """Copy `path` to backup_dir, mirroring its location under `root`."""
    dest = backup_dir / real(path).relative_to(real(root))
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy2(real(path), dest)
    return dest
