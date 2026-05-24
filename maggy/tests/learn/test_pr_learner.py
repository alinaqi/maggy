"""Tests for PR comment learner — remote parsing, signal extraction."""

from __future__ import annotations

import pytest

from maggy.learn.pr_learner import _parse_github_remote, extract_pr_signals


class TestParseGithubRemote:
    def test_ssh_remote(self):
        result = _parse_github_remote("git@github.com:alinaqi/maggy.git")
        assert result == ("alinaqi", "maggy")

    def test_ssh_no_git_suffix(self):
        result = _parse_github_remote("git@github.com:alinaqi/maggy")
        assert result == ("alinaqi", "maggy")

    def test_https_remote(self):
        result = _parse_github_remote("https://github.com/alinaqi/maggy.git")
        assert result == ("alinaqi", "maggy")

    def test_https_no_git_suffix(self):
        result = _parse_github_remote("https://github.com/alinaqi/maggy")
        assert result == ("alinaqi", "maggy")

    def test_gitlab_returns_none(self):
        result = _parse_github_remote("git@gitlab.com:org/repo.git")
        assert result is None

    def test_bitbucket_returns_none(self):
        result = _parse_github_remote("git@bitbucket.org:org/repo.git")
        assert result is None

    def test_empty_returns_none(self):
        result = _parse_github_remote("")
        assert result is None

    def test_nonsense_returns_none(self):
        result = _parse_github_remote("not a url at all")
        assert result is None


class TestExtractPrSignals:
    def test_extracts_comment_with_path(self):
        comments = [{"body": "This function needs error handling for edge cases", "path": "src/auth.py", "pr_number": 42}]
        sigs = extract_pr_signals(comments)
        assert len(sigs) == 1
        assert sigs[0]["memory_type"] == "feedback"
        assert "file:src/auth.py" in sigs[0]["tags"]
        assert "PR#42" in sigs[0]["content"]

    def test_skips_short_comments(self):
        comments = [{"body": "LGTM", "path": "a.py", "pr_number": 1}]
        sigs = extract_pr_signals(comments)
        assert len(sigs) == 0

    def test_skips_empty_body(self):
        comments = [{"body": "", "path": "a.py", "pr_number": 1}]
        sigs = extract_pr_signals(comments)
        assert len(sigs) == 0

    def test_caps_at_ten(self):
        comments = [
            {"body": f"Comment number {i} with enough detail to pass", "path": f"file{i}.py", "pr_number": i}
            for i in range(20)
        ]
        sigs = extract_pr_signals(comments)
        assert len(sigs) <= 10

    def test_content_truncated(self):
        comments = [{"body": "x" * 500, "path": "big.py", "pr_number": 1}]
        sigs = extract_pr_signals(comments)
        for s in sigs:
            assert len(s["content"]) <= 230

    def test_pr_review_tag(self):
        comments = [{"body": "Please add input validation here", "path": "api.py", "pr_number": 5}]
        sigs = extract_pr_signals(comments)
        assert "pr-review" in sigs[0]["tags"]
