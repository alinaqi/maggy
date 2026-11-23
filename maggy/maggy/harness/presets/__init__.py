"""Shipped profile presets: <name>.yaml (a profile layer) plus Markdown includes.

A profile includes a preset's Markdown as `preset:<file>` in instructions.include;
it resolves here, inside the installed package, not against the sources root.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from maggy.harness.errors import HarnessConfigError
from maggy.harness.schema import HarnessProfile

PRESETS_DIR = Path(__file__).resolve().parent
PREFIX = "preset:"


def available() -> list[str]:
    return sorted(path.stem for path in PRESETS_DIR.glob("*.yaml"))


def load_preset(name: str) -> dict:
    """The preset's profile layer; unknown names fail with the choices."""
    if name not in available():
        raise HarnessConfigError("--preset", [f"unknown preset {name!r}; choose one of: {', '.join(available())}"])
    data = yaml.safe_load((PRESETS_DIR / f"{name}.yaml").read_text(encoding="utf-8")) or {}
    HarnessProfile.model_validate(data)
    return data


def include_path(include: str) -> Path | None:
    """`preset:<file>` -> its path in this package (None when not a preset include)."""
    if not include.startswith(PREFIX):
        return None
    name = include[len(PREFIX):]
    path = (PRESETS_DIR / name).resolve()
    if path.parent != PRESETS_DIR or path.suffix != ".md" or not path.is_file():
        raise HarnessConfigError("<harness profile>", [f"instructions.include: no preset file {include!r}"])
    return path
