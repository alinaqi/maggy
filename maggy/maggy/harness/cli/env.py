"""What the harness CLI touches outside Python: subprocesses, PATH, HOME, sources.

Commands read a ToolEnv from the Typer context object (tests inject fakes);
without one they use the real environment. Every subprocess call is an argv
list, never a shell string.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import typer

from maggy.harness.emitters import EmitterSources, default_sources

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def run_argv(argv: list[str]) -> subprocess.CompletedProcess:
    """Run argv without a shell; a missing binary or timeout is a failed result."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


@dataclass
class ToolEnv:
    run: Runner = run_argv
    which: Callable[[str], str | None] = shutil.which
    home: Path = field(default_factory=Path.home)
    sources: EmitterSources = field(default_factory=default_sources)

    @property
    def state_dir(self) -> Path:
        return self.home / ".maggy"


def get_env(ctx: typer.Context) -> ToolEnv:
    found = ctx.find_object(ToolEnv)
    return found if found is not None else ToolEnv()
