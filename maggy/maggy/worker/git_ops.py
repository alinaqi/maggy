"""Runner-side git calls: argv lists only, hardened against repo-controlled config.

Hooks are disabled (`core.hooksPath=/dev/null`), signing and fsmonitor are off, system
config is ignored, and git runs with the scrubbed allowlist env (no AWG, GitHub or
provider credentials, no inherited GIT_* overrides), so even a filter or helper the
agent manages to get run never sees the runner's secrets (RFC §2.6.1).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from maggy.worker.env import allowlisted

HARDENING = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "core.fsmonitor=false"]
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


class GitError(RuntimeError):
    """A git command failed; the message carries its stderr."""


def run_git(cwd: Path, args: list[str], extra_env: dict[str, str] | None = None) -> str:
    """Run `git <args>` in `cwd` and return stripped stdout, or raise GitError."""
    env = {**allowlisted(os.environ), **GIT_ENV, **(extra_env or {})}
    done = subprocess.run(["git", *HARDENING, *args], cwd=cwd, env=env, capture_output=True,
                          text=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()
