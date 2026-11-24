"""The RED checkout: base commit plus ONLY the test files the candidate added or changed.

Source files stay at base, so a named test that passes there does not prove the change.
Test files are recognised by path (a tests/test/__tests__/e2e/spec directory, or a
test_*/ *_test / *.test.* / *.spec.* / conftest.py name). Contents come from the candidate
commit's blobs (`git cat-file`), never from the agent's worktree; deletions are not applied.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from maggy.worker.env import allowlisted
from maggy.worker.git_ops import GIT_ENV, HARDENING, GitError, run_git

TEST_DIRS = frozenset({"tests", "test", "__tests__", "e2e", "spec"})
TEST_NAME = re.compile(r"^(test_.+|.+_test\.[^.]+|.+\.(test|spec)\.[^.]+|conftest\.py)$")


def is_test_file(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool(TEST_DIRS.intersection(parts[:-1])) or bool(TEST_NAME.match(parts[-1]))


def changed_test_files(repo: Path, commits: tuple[str, str]) -> list[str]:
    """Test files added or modified between base and candidate, sorted."""
    listed = run_git(repo, ["diff", "--name-only", "--no-renames", "--diff-filter=AM", "-z",
                            commits[0], commits[1]])
    return sorted(name for name in listed.split("\0") if name and is_test_file(name))


def overlay_tests(repo: Path, commits: tuple[str, str], dest: Path) -> list[str]:
    """Write the candidate's changed test files into `dest` (a checkout of base)."""
    copied = changed_test_files(repo, commits)
    for name in copied:
        target = dest / name
        if not target.resolve().is_relative_to(dest.resolve()):
            raise GitError(f"refusing to overlay {name!r} outside the checkout")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_blob(repo, f"{commits[1]}:{name}"))
    return copied


def _blob(repo: Path, spec: str) -> bytes:
    """Raw blob bytes (run_git strips text), with the same hardening and scrubbed env."""
    done = subprocess.run(["git", *HARDENING, "cat-file", "blob", spec], cwd=repo,
                          env={**allowlisted(os.environ), **GIT_ENV}, capture_output=True,
                          check=False, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise GitError(f"git cat-file {spec} failed: {done.stderr.decode(errors='replace')}")
    return done.stdout
