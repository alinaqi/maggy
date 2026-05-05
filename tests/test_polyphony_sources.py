"""Tests for Polyphony work sources (§2)."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from polyphony.sources import get_source, list_sources
from polyphony.sources.local import LocalSource
from polyphony.sources.github import GitHubSource
from polyphony.models import Task


class TestRegistry:
    def test_list_sources(self):
        names = list_sources()
        assert "local" in names
        assert "github" in names

    def test_get_local_source(self):
        src = get_source("local")
        assert isinstance(src, LocalSource)

    def test_get_github_source(self):
        src = get_source("github")
        assert isinstance(src, GitHubSource)

    def test_unknown_raises(self):
        with pytest.raises(KeyError, match="jira"):
            get_source("jira")


class TestLocalSource:
    def test_add_and_poll(self, tmp_path):
        src = LocalSource(db_path=tmp_path / "queue.db")
        src.add_task("Fix typo", task_type="docs", risk="low")
        tasks = src.poll()
        assert len(tasks) == 1
        assert tasks[0].title == "Fix typo"
        assert tasks[0].source == "local"

    def test_poll_empty(self, tmp_path):
        src = LocalSource(db_path=tmp_path / "queue.db")
        assert src.poll() == []

    def test_mark_claimed(self, tmp_path):
        src = LocalSource(db_path=tmp_path / "queue.db")
        src.add_task("Task A")
        tasks = src.poll()
        src.mark_claimed(tasks[0].id)
        # After claiming, poll should not return it
        remaining = src.poll()
        assert len(remaining) == 0

    def test_multiple_tasks(self, tmp_path):
        src = LocalSource(db_path=tmp_path / "queue.db")
        src.add_task("Task A")
        src.add_task("Task B")
        src.add_task("Task C")
        tasks = src.poll()
        assert len(tasks) == 3


class TestGitHubSource:
    @patch("polyphony.sources.github._run_gh")
    def test_poll_returns_tasks(self, mock_gh):
        issues = [
            {
                "number": 42,
                "title": "Fix auth bug",
                "labels": [{"name": "agent-ready"}],
            },
        ]
        mock_gh.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(issues),
        )
        src = GitHubSource(repo="owner/repo")
        tasks = src.poll()
        assert len(tasks) == 1
        assert tasks[0].title == "Fix auth bug"
        assert tasks[0].source == "github"
        assert "42" in tasks[0].source_ref

    @patch("polyphony.sources.github._run_gh")
    def test_poll_empty(self, mock_gh):
        mock_gh.return_value = MagicMock(
            returncode=0, stdout="[]",
        )
        src = GitHubSource(repo="owner/repo")
        assert src.poll() == []

    @patch("polyphony.sources.github._run_gh")
    def test_poll_gh_failure(self, mock_gh):
        mock_gh.return_value = MagicMock(
            returncode=1, stderr="auth failed",
        )
        src = GitHubSource(repo="owner/repo")
        # Should return empty, not crash
        assert src.poll() == []

    @patch("polyphony.sources.github._run_gh")
    def test_label_filter(self, mock_gh):
        mock_gh.return_value = MagicMock(
            returncode=0, stdout="[]",
        )
        src = GitHubSource(
            repo="owner/repo",
            label_filter="polyphony",
        )
        src.poll()
        cmd = mock_gh.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "polyphony" in cmd_str
