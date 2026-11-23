"""Throwaway git repos, a fake file-editing agent CLI and profiles for runner-side tests."""

from __future__ import annotations

import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.worker.adapter_spec import AdapterSpec
from worker_helpers import adapter_data

# Edits a tracked file, adds a new one, touches CI config and writes an ignored file.
# The prompt "noop" makes it change nothing.
FAKE_AGENT = """
import sys
from pathlib import Path
if sys.argv[-1] == "noop":
    sys.exit(0)
Path("README.md").write_text("changed by agent\\n")
Path("new_file.txt").write_text("brand new\\n")
Path(".github/workflows/ci.yml").write_text("on: push  # agent edit\\n")
Path("build.log").write_text("ignored\\n")
print("done")
"""

# Dumps cwd, HEAD and the environment as JSON to argv[1]; exits with argv[2].
DUMP_CHECK = """
import json, os, subprocess, sys
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout
json.dump({"cwd": os.getcwd(), "head": head.strip(), "env": dict(os.environ)},
          open(sys.argv[1], "w"))
sys.exit(int(sys.argv[2]))
"""

GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *GIT_ID, *args], cwd=cwd, capture_output=True, text=True,
                          check=True)
    return done.stdout.strip()


def init_repo(path: Path) -> str:
    """A repo with README, CI config and .gitignore committed; returns HEAD."""
    (path / ".github" / "workflows").mkdir(parents=True)
    (path / "README.md").write_text("hello\n")
    (path / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    (path / ".gitignore").write_text("build.log\n")
    git(path, "init", "-q", "-b", "main")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    return git(path, "rev-parse", "HEAD")


def write_script(directory: Path, name: str, body: str) -> Path:
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(body))
    return path


def fake_adapter_data(script: Path, name: str = "fakeedit") -> dict:
    return adapter_data(name=name, detect=[sys.executable, "--version"],
                        argv=[sys.executable, str(script), "{prompt}"], output="text",
                        env={}, disable_awg={},
                        cost={"streams": False, "fixed_reservation_usd": 0.1})


def fake_adapter(script: Path) -> AdapterSpec:
    return AdapterSpec.model_validate(fake_adapter_data(script))


def dump_command(script: Path, out: Path, exit_code: int = 0) -> str:
    return shlex.join([sys.executable, str(script), str(out), str(exit_code)])


def profile_data(commands: dict | None = None, required: list[str] | None = None) -> dict:
    return {"permissions": {"profiles": {
                "read_only": {"write": False, "network": False, "shell": False},
                "workspace": {"write": "workspace", "network": False, "shell": "allowlist"}}},
            "worker": {"allow_host_execution": True},
            "commands": commands or {}, "validation": {"required": required or []},
            "risk": {"high": {"paths": ["src/payments/**"]}}}


def profile(commands: dict | None = None, required: list[str] | None = None) -> HarnessProfile:
    return HarnessProfile.model_validate(profile_data(commands, required))
