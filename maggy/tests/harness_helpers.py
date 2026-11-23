"""Shared fixtures for harness profile tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.safe_dump(data)
    path.write_text(text)
    return path


def repo_file(root: Path) -> Path:
    return root / ".maggy" / "harness.yaml"


def all_paths(data: dict, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        if isinstance(value, dict):
            paths |= all_paths(value, path)
    return paths
