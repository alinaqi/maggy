"""merge_changes captures every change made in an isolated workspace."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.orchestrator.merge import merge_changes
from maggy.orchestrator.worktree import create_worktree
from merge_helpers import commit, make_repo


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def test_captures_commits_uncommitted_and_untracked(repo, tmp_path):
    ws = create_worktree(repo, "s1", tmp_path / "ws")
    commit(ws, "one.txt", "first\n")
    commit(ws, "two.txt", "second\n")
    (ws / "a.txt").write_text("edited, not committed\n")
    (ws / "new.txt").write_text("untracked\n")
    (ws / "debug.log").write_text("ignored\n")
    assert merge_changes(repo, ws) is True
    assert (repo / "one.txt").read_text() == "first\n"
    assert (repo / "two.txt").read_text() == "second\n"
    assert (repo / "a.txt").read_text() == "edited, not committed\n"
    assert (repo / "new.txt").read_text() == "untracked\n"
    assert not (repo / "debug.log").exists()


def test_no_changes_is_success(repo, tmp_path):
    ws = create_worktree(repo, "s2", tmp_path / "ws")
    assert merge_changes(repo, ws) is True


def test_conflict_reports_failure(repo, tmp_path):
    ws = create_worktree(repo, "s3", tmp_path / "ws")
    (ws / "a.txt").write_text("workspace\n")
    (repo / "a.txt").write_text("repo dirty edit\n")
    assert merge_changes(repo, ws) is False


def test_missing_workspace_reports_failure(repo, tmp_path):
    assert merge_changes(repo, tmp_path / "nope") is False


def test_numstat_parser_keeps_spaces_and_tabs_in_names():
    from maggy.orchestrator.merge_rollback import _parse_numstat_z
    out = "1\t0\ta b.txt\0" "2\t1\told\tname\0" "-\t-\tbin.png\0"
    assert _parse_numstat_z(out) == ["a b.txt", "old\tname", "bin.png"]
