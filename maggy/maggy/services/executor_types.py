"""Executor shared types — context and step descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.providers.base import Task


@dataclass
class SessionCtx:
    """Bundles session state, task, and working dir for executor."""

    session: dict
    task: Task
    wd: str
    icpg: str = ""


@dataclass
class StepSpec:
    """Describes a single TDD pipeline step."""

    label: str
    prompt: str
    max_turns: int
