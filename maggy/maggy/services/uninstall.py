"""`maggy uninstall` — remove the assets `maggy bootstrap` installed.

Symmetric with bootstrap: it removes ONLY the asset names the source defines
(the skills / commands / hooks / ~bin wrappers / plugin folders it placed), so
it never touches the user's own files in ~/.claude, ~/bin, or ~/.maggy. The pip
package, the Maggy config + data, and any srooter shell routing are left alone
on purpose — see UNINSTALL.md for those manual steps.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from maggy.services.bootstrap import _plugins_src, _resolve_source


def _asset_names(src: Path, *, dirs_only: bool = False) -> list[str]:
    """Top-level asset names bootstrap would have placed from `src`."""
    if not src.is_dir():
        return []
    names = []
    for item in src.iterdir():
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        if dirs_only and not item.is_dir():
            continue
        names.append(item.name)
    return names


def _remove(target_dir: Path, names: list[str]) -> list[str]:
    """Remove each named entry from target_dir; return what was removed."""
    removed = []
    for name in names:
        p = target_dir / name
        if p.is_symlink() or p.is_file():
            p.unlink()
            removed.append(name)
        elif p.is_dir():
            shutil.rmtree(p)
            removed.append(name)
    return removed


def _targets(claude_home, bin_dir, plugins_dir):
    """Resolve the three install roots, defaulting to the standard locations."""
    return (
        claude_home or (Path.home() / ".claude"),
        bin_dir or (Path.home() / "bin"),
        plugins_dir or (Path.home() / ".maggy" / "plugins"),
    )


def _categories(src, claude_home, bin_dir, plugins_dir):
    """category -> (target_dir, asset_names) for every managed asset class.

    Covers both `maggy bootstrap` (skills/commands/hooks/bin/plugins) and the
    extra ~/.claude assets `install.sh` places (rules/templates). Missing source
    dirs yield no names, so a category is simply skipped when absent.
    """
    return {
        "skills": (claude_home / "skills", _asset_names(src / "skills")),
        "commands": (claude_home / "commands", _asset_names(src / "commands")),
        "hooks": (claude_home / "hooks", _asset_names(src / "hooks")),
        "rules": (claude_home / "rules", _asset_names(src / "rules")),
        "templates": (claude_home / "templates", _asset_names(src / "templates")),
        "bin": (bin_dir, _asset_names(src / "bin")),
        "plugins": (plugins_dir, _asset_names(_plugins_src(src), dirs_only=True)),
    }


def plan_uninstall(source=None, *, claude_home=None, bin_dir=None, plugins_dir=None) -> dict[str, list[str]]:
    """What uninstall WOULD remove, per category — only entries that exist."""
    src = _resolve_source(source)
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    cats = _categories(src, claude_home, bin_dir, plugins_dir)
    return {cat: [n for n in names if (tdir / n).exists()] for cat, (tdir, names) in cats.items()}


def run_uninstall(
    source=None, *, claude_home=None, bin_dir=None, plugins_dir=None, remove_marker=True,
) -> dict[str, list[str]]:
    """Remove bootstrap-installed assets. Returns what was removed per category."""
    src = _resolve_source(source)
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    cats = _categories(src, claude_home, bin_dir, plugins_dir)
    result = {cat: _remove(tdir, names) for cat, (tdir, names) in cats.items()}
    marker = claude_home / ".bootstrap-dir"
    if remove_marker and marker.exists():
        marker.unlink()
        result["marker"] = [".bootstrap-dir"]
    return result
