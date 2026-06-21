"""Backup / restore / diff for the install footprint.

Before Maggy overwrites anything, it can snapshot the user's *existing* files so
the original state is recoverable. A backup captures:
  - `~/.claude/settings.json` (the highest-value user file), and
  - every pre-existing file Maggy would overwrite (a *collision* — a file the
    user already had at a managed asset path).

Maggy's own new files aren't captured (they restore via `maggy uninstall`). The
snapshot mirrors the home layout under `~/.maggy/backups/<id>/`, so restore is a
plain merge-copy back. `diff_install` shows what an install would add/change.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from maggy.services.bootstrap import _plugins_src, _resolve_source
from maggy.services.uninstall import _categories, _targets

# managed category -> where it lives under a backup dir (mirrors $HOME layout)
_REL = {
    "skills": "claude/skills", "commands": "claude/commands", "hooks": "claude/hooks",
    "rules": "claude/rules", "templates": "claude/templates",
    "bin": "bin", "plugins": "maggy/plugins",
}


def _backups_dir(backups_dir: Path | None) -> Path:
    return backups_dir or (Path.home() / ".maggy" / "backups")


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _stash(src_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if src_path.is_dir():
        shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
    else:
        shutil.copy2(src_path, dest_path)


def collisions(source=None, *, claude_home=None, bin_dir=None, plugins_dir=None) -> dict[str, list[str]]:
    """User's pre-existing files that an install would overwrite, per category."""
    src = _resolve_source(source)
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    cats = _categories(src, claude_home, bin_dir, plugins_dir)
    return {cat: [n for n in names if (tdir / n).exists()] for cat, (tdir, names) in cats.items()}


def create_backup(
    source=None, *, claude_home=None, bin_dir=None, plugins_dir=None,
    backups_dir=None, backup_id=None,
) -> dict:
    """Snapshot settings.json + collisions into ~/.maggy/backups/<id>/."""
    src = _resolve_source(source)
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    dest = _backups_dir(backups_dir) / (backup_id or _now_id())
    captured: dict[str, list[str]] = {}

    settings = claude_home / "settings.json"
    if settings.exists():
        _stash(settings, dest / "claude" / "settings.json")
        captured["settings"] = ["settings.json"]

    for cat, (tdir, names) in _categories(src, claude_home, bin_dir, plugins_dir).items():
        hit = [n for n in names if (tdir / n).exists()]
        for n in hit:
            _stash(tdir / n, dest / _REL[cat] / n)
        if hit:
            captured[cat] = hit

    manifest = {"id": dest.name, "source": str(src), "captured": captured}
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def list_backups(backups_dir=None) -> list[dict]:
    """Manifests of all backups, newest first."""
    bdir = _backups_dir(backups_dir)
    if not bdir.is_dir():
        return []
    out = []
    for d in sorted((p for p in bdir.iterdir() if p.is_dir()), reverse=True):
        m = d / "manifest.json"
        if m.exists():
            out.append(json.loads(m.read_text()))
    return out


def _merge_copy(snap_dir: Path, target_dir: Path) -> int:
    """Copy every file under snap_dir back into target_dir (overwriting)."""
    if not snap_dir.is_dir():
        return 0
    n = 0
    for item in snap_dir.rglob("*"):
        if item.is_file():
            dst = target_dir / item.relative_to(snap_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)
            n += 1
    return n


def restore_backup(
    backup_id=None, *, claude_home=None, bin_dir=None, plugins_dir=None, backups_dir=None,
) -> dict:
    """Restore a backup (latest if id omitted). Returns files restored."""
    backups = list_backups(backups_dir)
    if not backups:
        raise FileNotFoundError("no backups found")
    chosen = backup_id or backups[0]["id"]
    dest = _backups_dir(backups_dir) / chosen
    if not (dest / "manifest.json").exists():
        raise FileNotFoundError(f"backup not found: {chosen}")
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    restored = (
        _merge_copy(dest / "claude", claude_home)
        + _merge_copy(dest / "bin", bin_dir)
        + _merge_copy(dest / "maggy" / "plugins", plugins_dir)
    )
    return {"id": chosen, "restored": restored}


def _entries_equal(a: Path, b: Path) -> bool:
    """Deep content compare of two files or two directories (skips __pycache__)."""
    if a.is_dir() and b.is_dir():
        af = {p.relative_to(a): p for p in a.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        bf = {p.relative_to(b): p for p in b.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        return set(af) == set(bf) and all(af[k].read_bytes() == bf[k].read_bytes() for k in af)
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


def _classify(src_entry: Path, tgt_entry: Path) -> str:
    if not tgt_entry.exists():
        return "add"
    return "same" if _entries_equal(src_entry, tgt_entry) else "change"


def diff_install(source=None, *, claude_home=None, bin_dir=None, plugins_dir=None) -> dict:
    """What `maggy bootstrap` would do per asset: add (new) / change (overwrite) / same."""
    src = _resolve_source(source)
    claude_home, bin_dir, plugins_dir = _targets(claude_home, bin_dir, plugins_dir)
    src_dirs = {
        "skills": src / "skills", "commands": src / "commands", "hooks": src / "hooks",
        "rules": src / "rules", "templates": src / "templates",
        "bin": src / "bin", "plugins": _plugins_src(src),
    }
    out: dict[str, dict[str, list[str]]] = {}
    for cat, (tdir, names) in _categories(src, claude_home, bin_dir, plugins_dir).items():
        buckets: dict[str, list[str]] = {"add": [], "change": [], "same": []}
        for n in names:
            buckets[_classify(src_dirs[cat] / n, tdir / n)].append(n)
        out[cat] = buckets
    return out
