"""The coupon fixture app reproduces the factory doc's bug, and the agent's fix diff fixes it:
each planned browser test fails by an assertion on the buggy checkout and passes once
fix.diff is applied (what the exit test's RED/GREEN proof relies on)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from coupon_helpers import FIXTURE, TESTS, seed_app
from verify_helpers import browser  # noqa: F401 - the skip-or-run fixture

AGENT = FIXTURE / "agent"


def _checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "app"
    (repo / "tests").mkdir(parents=True)
    seed_app(repo)
    for source in AGENT.glob("*.py.txt"):
        shutil.copyfile(source, repo / "tests" / source.name.removesuffix(".txt"))
    return repo


def _pytest(repo: Path) -> subprocess.CompletedProcess:
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    return subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=False,
                          env=dict(os.environ), timeout=300)


def test_buggy_checkout_fails_every_planned_test_by_assertion(tmp_path: Path, browser) -> None:
    done = _pytest(_checkout(tmp_path))
    assert done.returncode == 1, done.stdout + done.stderr
    assert "4 failed" in done.stdout, done.stdout
    assert "AssertionError" in done.stdout and "no field error" in done.stdout
    for test in TESTS.values():
        assert test in done.stdout


def test_fix_diff_makes_every_planned_test_pass(tmp_path: Path, browser) -> None:
    repo = _checkout(tmp_path)
    subprocess.run(["git", "apply", str(AGENT / "fix.diff")], cwd=repo, check=True)
    done = _pytest(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "4 passed" in done.stdout, done.stdout
