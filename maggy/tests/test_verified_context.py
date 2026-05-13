"""Tests for verified context — git state + session data."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.services.verified_context import (
    VerifiedContext,
    format_verified,
    gather_verified,
)


def test_verified_context_fields():
    """VerifiedContext has all required fields."""
    ctx = VerifiedContext(
        branch="main",
        status_summary="2 modified, 1 untracked",
        recent_commits=["abc Fix bug", "def Add test"],
        active_sessions=[{"provider": "claude"}],
    )
    assert ctx.branch == "main"
    assert len(ctx.recent_commits) == 2
    assert ctx.active_sessions[0]["provider"] == "claude"


def test_format_verified_includes_branch():
    """Format includes git branch."""
    ctx = VerifiedContext(
        branch="feat/auth",
        status_summary="clean",
        recent_commits=["abc Fix auth"],
        active_sessions=[],
    )
    text = format_verified(ctx)
    assert "feat/auth" in text


def test_format_verified_includes_commits():
    """Format includes recent commits."""
    ctx = VerifiedContext(
        branch="main",
        status_summary="clean",
        recent_commits=["abc1234 Fix login", "def5678 Add tests"],
        active_sessions=[],
    )
    text = format_verified(ctx)
    assert "Fix login" in text
    assert "Add tests" in text


def test_format_verified_includes_sessions():
    """Format includes active sessions."""
    ctx = VerifiedContext(
        branch="main",
        status_summary="clean",
        recent_commits=[],
        active_sessions=[
            {"provider": "claude", "pid": "123"},
        ],
    )
    text = format_verified(ctx)
    assert "claude" in text


def test_format_verified_empty_context():
    """Empty context produces minimal output."""
    ctx = VerifiedContext(
        branch="",
        status_summary="",
        recent_commits=[],
        active_sessions=[],
    )
    text = format_verified(ctx)
    assert text == ""


def test_gather_verified_in_git_repo(tmp_path: Path):
    """gather_verified reads git state from a real repo."""
    # Create a minimal git repo
    import subprocess
    subprocess.run(
        ["git", "init"], cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True,
    )
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "."], cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path, capture_output=True,
    )
    ctx = gather_verified(str(tmp_path))
    assert ctx.branch != ""
    assert len(ctx.recent_commits) >= 1
    assert "Initial commit" in ctx.recent_commits[0]


def test_gather_verified_not_git(tmp_path: Path):
    """Non-git directory returns empty context."""
    ctx = gather_verified(str(tmp_path))
    assert ctx.branch == ""
    assert ctx.recent_commits == []
