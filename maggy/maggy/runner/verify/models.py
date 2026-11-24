"""Shared shapes of the verify checks: the candidate job and one viewport's verdict."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from maggy.harness.schema import HarnessProfile

Verdict = Literal["PASS", "FAIL", "PENDING"]


@dataclass(frozen=True)
class VisualJob:
    repo: Path
    sha: str
    work_dir: Path
    profile: HarnessProfile


@dataclass(frozen=True)
class ViewResult:
    criterion_id: str
    viewport: str
    verdict: Verdict
    reason: str = ""
    artifacts: dict[str, Path] = field(default_factory=dict)
    check: str = "visual"  # functional, visual or vision
