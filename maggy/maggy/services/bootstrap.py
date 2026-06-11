"""`maggy bootstrap` — install the claude-bootstrap assets from a checkout.

A pip-installed `maggy-harness` ships the server + dashboard + CLI, but the
broader value (skills, hooks, slash commands, the ~/bin model wrappers, and
plugins) lives in the claude-bootstrap repo. This installs those into the
standard locations so `pip install` + `maggy bootstrap` = the full setup.

Idempotent and non-destructive-ish: it overwrites managed asset files but never
deletes user files it didn't place.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


class BootstrapError(Exception):
    """Raised when no bootstrap source can be resolved."""


def _resolve_source(source: Path | str | None) -> Path:
    """Find a claude-bootstrap checkout: arg → env → marker."""
    if source:
        return Path(source).expanduser().resolve()
    env = os.environ.get("MAGGY_BOOTSTRAP_DIR")
    if env:
        return Path(env).expanduser().resolve()
    marker = Path.home() / ".claude" / ".bootstrap-dir"
    if marker.exists():
        return Path(marker.read_text().strip()).expanduser().resolve()
    raise BootstrapError(
        "No bootstrap source found. Clone the repo and point at it:\n"
        "  git clone https://github.com/alinaqi/maggy ~/maggy-src\n"
        "  maggy bootstrap --source ~/maggy-src\n"
        "or set MAGGY_BOOTSTRAP_DIR."
    )


def _copy_tree(src: Path, dst: Path) -> int:
    """Copy each top-level entry of src into dst. Returns items copied."""
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in src.iterdir():
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
        n += 1
    return n


def _plugins_src(source: Path) -> Path:
    """Plugins live at <root>/plugins or, in this repo, <root>/maggy/plugins."""
    top = source / "plugins"
    if top.is_dir() and any(p.is_dir() for p in top.iterdir()):
        return top
    nested = source / "maggy" / "plugins"
    return nested if nested.is_dir() else top


def _copy_plugins(src: Path, dst: Path) -> int:
    """Copy plugin FOLDERS only (skip the package loader: __init__/manager)."""
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in src.iterdir():
        if not item.is_dir() or item.name in ("__pycache__",):
            continue
        shutil.copytree(item, dst / item.name, dirs_exist_ok=True)
        n += 1
    return n


def _copy_executables(src: Path, dst: Path) -> int:
    """Copy bin wrappers and mark them executable."""
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in src.iterdir():
        if item.is_file() and not item.name.startswith("."):
            target = dst / item.name
            shutil.copy2(item, target)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
            n += 1
    return n


def run_bootstrap(
    source: Path | str | None = None,
    *,
    claude_home: Path | None = None,
    bin_dir: Path | None = None,
    plugins_dir: Path | None = None,
) -> dict[str, int]:
    """Install skills, commands, hooks, ~/bin wrappers, and plugins.

    Returns a count of items installed per asset type.
    """
    src = _resolve_source(source)
    claude_home = claude_home or (Path.home() / ".claude")
    bin_dir = bin_dir or (Path.home() / "bin")
    plugins_dir = plugins_dir or (Path.home() / ".maggy" / "plugins")

    result = {
        "skills": _copy_tree(src / "skills", claude_home / "skills"),
        "commands": _copy_tree(src / "commands", claude_home / "commands"),
        "hooks": _copy_tree(src / "hooks", claude_home / "hooks"),
        "bin": _copy_executables(src / "bin", bin_dir),
        "plugins": _copy_plugins(_plugins_src(src), plugins_dir),
    }
    claude_home.mkdir(parents=True, exist_ok=True)
    (claude_home / ".bootstrap-dir").write_text(str(src))
    return result
