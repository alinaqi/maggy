"""Mode detection — determines prompt behavior from working directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_PROJECT_MARKERS = [
    "CLAUDE.md", ".claude/CLAUDE.md",
    "pyproject.toml", "package.json",
    "Cargo.toml", "go.mod", "Gemfile",
    "pom.xml", "build.gradle",
]


class Mode(Enum):
    PROJECT = "project"
    WORKSPACE = "workspace"
    BOOTSTRAP = "bootstrap"


@dataclass
class DetectedMode:
    mode: Mode
    confidence: float
    markers: list[str] = field(default_factory=list)


def detect_mode(working_dir: str) -> DetectedMode:
    root = Path(working_dir)
    markers = _find_markers(root)
    if markers:
        confidence = min(round(0.7 + 0.1 * len(markers), 2), 1.0)
        return DetectedMode(Mode.PROJECT, confidence, markers)
    if (root / ".git").is_dir():
        return DetectedMode(Mode.WORKSPACE, 0.6, [".git"])
    return DetectedMode(Mode.BOOTSTRAP, 0.3, [])


def _find_markers(root: Path) -> list[str]:
    found: list[str] = []
    for name in _PROJECT_MARKERS:
        if (root / name).exists():
            found.append(name)
    return found
