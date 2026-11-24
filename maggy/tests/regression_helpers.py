"""Tiny fixture repos and profiles for the AC-aware RED/GREEN regression proof tests."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from worker_git_helpers import git, profile_data

CALC_BUGGY = "def add(a, b):\n    return a - b\n"
CALC_FIXED = "def add(a, b):\n    return a + b\n"
TEST_ADD = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
TEST_ZERO = "from calc import add\n\n\ndef test_add():\n    assert add(0, 0) == 0\n"
TEST_IMPORT = "from calc import mul\n\n\ndef test_add():\n    assert mul(2, 3) == 6\n"
TEST_FIXTURE = ("from calc import add\n\n\ndef test_add(coupon_db):\n"
                "    assert add(2, 3) == 5\n")
PYTEST = f"{shlex.quote(sys.executable)} -m pytest"


def write_files(root: Path, files: dict[str, str]) -> None:
    for name, body in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(body)


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def fixture_repo(tmp_path: Path, candidate: dict[str, str]) -> tuple[Path, str, str]:
    """(repo, base, candidate): base has the buggy calc.py; the candidate commit adds files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write_files(repo, {"calc.py": CALC_BUGGY, "README.md": "base\n"})
    base = commit_all(repo, "base")
    write_files(repo, candidate)
    return repo, base, commit_all(repo, "candidate")


def regression_profile(regression: dict | None = None) -> HarnessProfile:
    data = profile_data()
    data["validation"]["regression"] = regression or {"runner": "pytest", "command": PYTEST}
    return HarnessProfile.model_validate(data)


def plan_entry(criterion: str = "AC1", test: str = "test_add") -> dict:
    return {"criterion_id": criterion, "task": "T1", "fixture": "calc", "action": "add",
            "expected": "sum", "evidence": "unit", "regression_test_name": test}
