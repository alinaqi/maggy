"""The RED worktree: base commit plus ONLY the test files the candidate added or changed."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.regression.overlay import is_test_file, overlay_tests
from maggy.worker.worktree import add_detached
from regression_helpers import CALC_BUGGY, CALC_FIXED, TEST_ADD, commit_all, fixture_repo
from worker_git_helpers import git


@pytest.mark.parametrize(("path", "expected"), [
    ("tests/test_calc.py", True), ("test_calc.py", True), ("calc_test.py", True),
    ("tests/conftest.py", True), ("web/__tests__/cart.js", True), ("src/cart.test.ts", True),
    ("e2e/coupon.spec.ts", True), ("tests/fixtures/data.json", True),
    ("calc.py", False), ("src/contest.py", False), ("README.md", False),
    ("src/testing_utils.py", False)])
def test_test_file_patterns(path: str, expected: bool) -> None:
    assert is_test_file(path) is expected


def test_overlay_copies_only_candidate_test_files(tmp_path: Path) -> None:
    repo, base, candidate = fixture_repo(tmp_path, {
        "calc.py": CALC_FIXED, "README.md": "candidate\n", "tests/test_calc.py": TEST_ADD,
        "tests/conftest.py": "# fixtures\n"})
    dest = add_detached(repo, base, tmp_path / "red")
    copied = overlay_tests(repo, (base, candidate), dest)
    assert copied == ["tests/conftest.py", "tests/test_calc.py"]
    assert (dest / "tests" / "test_calc.py").read_text() == TEST_ADD
    assert (dest / "calc.py").read_text() == CALC_BUGGY, "source stays at base"
    assert (dest / "README.md").read_text() == "base\n"
    assert git(dest, "rev-parse", "HEAD") == base


def test_overlay_ignores_deleted_test_files(tmp_path: Path) -> None:
    repo, _, first = fixture_repo(tmp_path, {"tests/test_old.py": "def test_x(): pass\n"})
    git(repo, "rm", "-q", "tests/test_old.py")
    candidate = commit_all(repo, "drop old test")
    dest = add_detached(repo, first, tmp_path / "red")
    assert overlay_tests(repo, (first, candidate), dest) == []
    assert (dest / "tests" / "test_old.py").exists(), "nothing is deleted from the base tree"
