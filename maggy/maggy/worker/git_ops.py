"""Runner-side git calls: argv lists only, hardened against repo-controlled config.

Hooks are disabled (`core.hooksPath=/dev/null`) and signing is off, so nothing the
agent planted in the repo runs with the runner's full environment.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

HARDENING = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "core.fsmonitor=false"]


class GitError(RuntimeError):
    """A git command failed; the message carries its stderr."""


def run_git(cwd: Path, args: list[str], extra_env: dict[str, str] | None = None) -> str:
    """Run `git <args>` in `cwd` and return stripped stdout, or raise GitError."""
    env = {**os.environ, **(extra_env or {})}
    done = subprocess.run(["git", *HARDENING, *args], cwd=cwd, env=env, capture_output=True,
                          text=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()
