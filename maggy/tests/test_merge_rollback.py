"""A failed 3-way merge leaves the repo exactly as it was (merge_rollback)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from maggy.orchestrator.merge import merge_changes
from maggy.orchestrator.worktree import create_worktree
from merge_helpers import git, make_repo, three_line_repo


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def test_content_conflict_leaves_repo_untouched(repo, tmp_path):
    three_line_repo(repo)
    ws1 = create_worktree(repo, "c1", tmp_path / "ws")
    ws2 = create_worktree(repo, "c2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("1\nONE\n3\n")
    (ws2 / "a.txt").write_text("1\nTWO\n3\nextra\n")
    (ws2 / "b.txt").write_text("new from ws2\n")
    assert merge_changes(repo, ws1) is True
    before = git(repo, "status", "--porcelain")
    assert merge_changes(repo, ws2) is False
    assert (repo / "a.txt").read_text() == "1\nONE\n3\n"
    assert not (repo / "b.txt").exists()
    assert git(repo, "status", "--porcelain") == before
    assert git(repo, "ls-files", "-u") == ""


def test_non_overlapping_sibling_edits_still_merge(repo, tmp_path):
    (repo / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\n8\n")
    git(repo, "commit", "-qam", "eight lines")
    ws1 = create_worktree(repo, "n1", tmp_path / "ws")
    ws2 = create_worktree(repo, "n2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("ONE\n2\n3\n4\n5\n6\n7\n8\n")
    (ws2 / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\nEIGHT\n")
    assert merge_changes(repo, ws1) is True
    assert merge_changes(repo, ws2) is True
    assert (repo / "a.txt").read_text() == "ONE\n2\n3\n4\n5\n6\n7\nEIGHT\n"


def test_failed_rename_merge_restores_both_paths(repo, tmp_path):
    three_line_repo(repo)
    ws1 = create_worktree(repo, "r1", tmp_path / "ws")
    ws2 = create_worktree(repo, "r2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("1\nONE\n3\n")
    git(ws2, "mv", "a.txt", "moved.txt")
    (ws2 / "moved.txt").write_text("1\nTWO\n3\n")
    assert merge_changes(repo, ws1) is True
    before = git(repo, "status", "--porcelain")
    assert merge_changes(repo, ws2) is False
    assert (repo / "a.txt").read_text() == "1\nONE\n3\n"
    assert not (repo / "moved.txt").exists()
    assert git(repo, "status", "--porcelain") == before


def test_failed_merge_restores_changed_symlink(repo, tmp_path):
    three_line_repo(repo)
    os.symlink("a.txt", repo / "link")
    git(repo, "add", "link")
    git(repo, "commit", "-qm", "link")
    ws1 = create_worktree(repo, "l1", tmp_path / "ws")
    ws2 = create_worktree(repo, "l2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("1\nONE\n3\n")
    (ws2 / "a.txt").write_text("1\nTWO\n3\n")
    (ws2 / "link").unlink()
    os.symlink("elsewhere.txt", ws2 / "link")
    assert merge_changes(repo, ws1) is True
    before = git(repo, "status", "--porcelain")
    assert merge_changes(repo, ws2) is False
    assert os.readlink(repo / "link") == "a.txt"
    assert (repo / "a.txt").read_text() == "1\nONE\n3\n"
    assert git(repo, "status", "--porcelain") == before
