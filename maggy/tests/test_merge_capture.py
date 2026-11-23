"""merge_changes captures every change made in an isolated workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maggy.orchestrator.merge import merge_changes
from maggy.orchestrator.worktree import create_worktree


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("base\n")
    (root / ".gitignore").write_text("*.log\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _commit(ws: Path, name: str, text: str) -> None:
    (ws / name).write_text(text)
    _git(ws, "add", name)
    _git(ws, "commit", "-qm", f"add {name}")


def test_captures_commits_uncommitted_and_untracked(repo, tmp_path):
    ws = create_worktree(repo, "s1", tmp_path / "ws")
    _commit(ws, "one.txt", "first\n")
    _commit(ws, "two.txt", "second\n")
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


def _three_line_repo(repo: Path) -> None:
    (repo / "a.txt").write_text("1\n2\n3\n")
    _git(repo, "commit", "-qam", "three lines")


def test_content_conflict_leaves_repo_untouched(repo, tmp_path):
    _three_line_repo(repo)
    ws1 = create_worktree(repo, "c1", tmp_path / "ws")
    ws2 = create_worktree(repo, "c2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("1\nONE\n3\n")
    (ws2 / "a.txt").write_text("1\nTWO\n3\nextra\n")
    (ws2 / "b.txt").write_text("new from ws2\n")
    assert merge_changes(repo, ws1) is True
    before = _git(repo, "status", "--porcelain")
    assert merge_changes(repo, ws2) is False
    assert (repo / "a.txt").read_text() == "1\nONE\n3\n"
    assert not (repo / "b.txt").exists()
    assert _git(repo, "status", "--porcelain") == before
    assert _git(repo, "ls-files", "-u") == ""


def test_non_overlapping_sibling_edits_still_merge(repo, tmp_path):
    (repo / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\n8\n")
    _git(repo, "commit", "-qam", "eight lines")
    ws1 = create_worktree(repo, "n1", tmp_path / "ws")
    ws2 = create_worktree(repo, "n2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("ONE\n2\n3\n4\n5\n6\n7\n8\n")
    (ws2 / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\nEIGHT\n")
    assert merge_changes(repo, ws1) is True
    assert merge_changes(repo, ws2) is True
    assert (repo / "a.txt").read_text() == "ONE\n2\n3\n4\n5\n6\n7\nEIGHT\n"


def test_failed_rename_merge_restores_both_paths(repo, tmp_path):
    _three_line_repo(repo)
    ws1 = create_worktree(repo, "r1", tmp_path / "ws")
    ws2 = create_worktree(repo, "r2", tmp_path / "ws")
    (ws1 / "a.txt").write_text("1\nONE\n3\n")
    _git(ws2, "mv", "a.txt", "moved.txt")
    (ws2 / "moved.txt").write_text("1\nTWO\n3\n")
    assert merge_changes(repo, ws1) is True
    before = _git(repo, "status", "--porcelain")
    assert merge_changes(repo, ws2) is False
    assert (repo / "a.txt").read_text() == "1\nONE\n3\n"
    assert not (repo / "moved.txt").exists()
    assert _git(repo, "status", "--porcelain") == before


def test_numstat_parser_keeps_spaces_and_tabs_in_names():
    from maggy.orchestrator.merge_rollback import _parse_numstat_z
    out = "1\t0\ta b.txt\0" "2\t1\told\tname\0" "-\t-\tbin.png\0"
    assert _parse_numstat_z(out) == ["a b.txt", "old\tname", "bin.png"]
