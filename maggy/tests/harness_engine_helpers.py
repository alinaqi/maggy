"""Shared fixtures for the harness managed-regions engine tests."""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import HarnessContext, ManagedFile


def make_ctx(tmp_path: Path, resolution: str | None = None) -> HarnessContext:
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    return HarnessContext(
        root=root, lock_path=tmp_path / "state" / "harness.lock",
        backups_dir=tmp_path / "state" / "backups", resolution=resolution,
    )


FORMATS = {".md": "markdown", ".json": "json", ".jsonc": "json", ".toml": "toml"}


def managed(ctx: HarnessContext, name: str, regions: dict) -> ManagedFile:
    fmt = FORMATS.get(Path(name).suffix, "text")
    return ManagedFile(path=ctx.root / name, format=fmt, regions=regions)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
