"""Tests for error pattern learner."""

from __future__ import annotations

import pytest

from maggy.learn.error_learner import build_error_signal


def test_builds_signal_with_class_tag():
    sig = build_error_signal("overload", "API overloaded", True)
    assert sig["memory_type"] == "fact"
    assert "class:overload" in sig["tags"]


def test_recovery_succeeded_tag():
    sig = build_error_signal("session", "not found", True)
    assert "recovered" in sig["tags"]


def test_recovery_failed_tag():
    sig = build_error_signal("generic", "unknown", False)
    assert "unrecovered" in sig["tags"]


def test_content_includes_error_class():
    sig = build_error_signal("context", "too long", True)
    assert "context" in sig["content"].lower()


def test_content_truncated():
    long_content = "x" * 500
    sig = build_error_signal("generic", long_content, True)
    assert len(sig["content"]) < 300


def test_confidence_is_one():
    sig = build_error_signal("session", "expired", True)
    assert sig["confidence"] == 1.0


def test_has_error_pattern_tag():
    sig = build_error_signal("overload", "rate limit", False)
    assert "error-pattern" in sig["tags"]
