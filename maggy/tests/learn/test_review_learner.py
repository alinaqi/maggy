"""Tests for review feedback learner."""

from __future__ import annotations

import pytest

from maggy.learn.review_learner import extract_review_signals


def test_detects_bug_issue():
    content = "There is a bug in the auth flow. The token validation is incorrect."
    sigs = extract_review_signals(content, "deepseek", "review")
    assert any(s["memory_type"] == "fact" and "issue" in s["tags"] for s in sigs)


def test_detects_vulnerability():
    content = "This has a security vulnerability due to missing input sanitization."
    sigs = extract_review_signals(content, "kimi", "review")
    assert any("issue" in s["tags"] for s in sigs)


def test_detects_suggestion():
    content = "You should consider using connection pooling for better performance."
    sigs = extract_review_signals(content, "codex", "review")
    assert any(s["memory_type"] == "decision" and "suggestion" in s["tags"] for s in sigs)


def test_detects_refactor_suggestion():
    content = "Consider refactoring this into a separate service module."
    sigs = extract_review_signals(content, "deepseek", "review")
    assert any("suggestion" in s["tags"] for s in sigs)


def test_ignores_short_sentences():
    content = "OK. Fine. Good."
    sigs = extract_review_signals(content, "kimi", "review")
    assert len(sigs) == 0


def test_max_five_signals():
    content = ". ".join([
        f"Bug {i} is a vulnerability that should be fixed" for i in range(20)
    ])
    sigs = extract_review_signals(content, "codex", "review")
    assert len(sigs) <= 5


def test_model_in_tags():
    content = "There is a missing error check in the handler."
    sigs = extract_review_signals(content, "deepseek-pro", "review")
    for s in sigs:
        assert "deepseek-pro" in s["tags"]


def test_empty_content():
    sigs = extract_review_signals("", "kimi", "review")
    assert len(sigs) == 0


def test_content_truncated():
    content = "There is a bug " + "x" * 500 + " end."
    sigs = extract_review_signals(content, "kimi", "review")
    for s in sigs:
        assert len(s["content"]) <= 220
