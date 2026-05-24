"""Tests for chat interaction learner — regex patterns, false positives, caps."""

from __future__ import annotations

import pytest

from maggy.learn.chat_learner import extract_signals, MIN_MSG_LENGTH


class TestCorrectionDetection:
    def test_explicit_no_with_context(self):
        sigs = extract_signals("no, don't mock the database", "", False)
        assert any(s["memory_type"] == "feedback" and "correction" in s["tags"] for s in sigs)

    def test_stop_doing(self):
        sigs = extract_signals("stop doing that, use the real API", "", False)
        assert any("correction" in s["tags"] for s in sigs)

    def test_instead_with_context(self):
        sigs = extract_signals("instead, use pathlib for file operations", "", False)
        assert any("correction" in s["tags"] for s in sigs)

    def test_actually_with_context(self):
        sigs = extract_signals("actually, that's not right — use async", "", False)
        assert any("correction" in s["tags"] for s in sigs)

    def test_dont_with_context(self):
        sigs = extract_signals("don't add error handling there", "", False)
        assert any("correction" in s["tags"] for s in sigs)


class TestFalsePositivePrevention:
    def test_bare_no_too_short(self):
        sigs = extract_signals("no", "", False)
        assert len(sigs) == 0

    def test_bare_yes_too_short(self):
        sigs = extract_signals("yes", "", False)
        assert len(sigs) == 0

    def test_notify_me_not_correction(self):
        sigs = extract_signals("notify me when the build completes", "", False)
        assert not any("correction" in s.get("tags", []) for s in sigs)

    def test_question_with_no(self):
        sigs = extract_signals("is there no way to fix this bug?", "", False)
        assert not any("correction" in s.get("tags", []) for s in sigs)

    def test_i_always_forget_not_preference(self):
        sigs = extract_signals("I always forget how this works", "", False)
        assert not any("preference" in s.get("tags", []) for s in sigs)

    def test_never_mind_not_preference(self):
        sigs = extract_signals("never mind that error message", "", False)
        assert not any("preference" in s.get("tags", []) for s in sigs)

    def test_empty_message(self):
        sigs = extract_signals("", "", False)
        assert len(sigs) == 0

    def test_whitespace_only(self):
        sigs = extract_signals("   ", "", False)
        assert len(sigs) == 0


class TestPreferenceDetection:
    def test_i_prefer(self):
        sigs = extract_signals("I prefer functional style over OOP", "", False)
        assert any(s["memory_type"] == "preference" for s in sigs)

    def test_i_always_want(self):
        sigs = extract_signals("I always want tests written first", "", False)
        assert any("preference" in s["tags"] for s in sigs)

    def test_please_dont(self):
        sigs = extract_signals("please don't add comments to the code", "", False)
        assert any("preference" in s["tags"] for s in sigs)

    def test_always_use(self):
        sigs = extract_signals("always use type hints in Python code", "", False)
        assert any("preference" in s["tags"] for s in sigs)


class TestPositiveConfirmation:
    def test_perfect(self):
        sigs = extract_signals("perfect, that's exactly what I needed", "", False)
        assert any("positive" in s["tags"] for s in sigs)

    def test_exactly(self):
        sigs = extract_signals("exactly, keep doing it that way", "", False)
        assert any("positive" in s["tags"] for s in sigs)

    def test_thats_right(self):
        sigs = extract_signals("that's right, good approach", "", False)
        assert any("positive" in s["tags"] for s in sigs)

    def test_yes_exactly(self):
        sigs = extract_signals("yes, exactly what I wanted", "", False)
        assert any("positive" in s["tags"] for s in sigs)


class TestErrorPattern:
    def test_error_always_recorded(self):
        sigs = extract_signals("tell me about the weather forecast today", "", True)
        assert any(s["memory_type"] == "fact" and "error-pattern" in s["tags"] for s in sigs)

    def test_no_error_no_signal(self):
        sigs = extract_signals("tell me about the weather forecast today", "", False)
        assert not any("error-pattern" in s.get("tags", []) for s in sigs)


class TestCaps:
    def test_max_three_signals(self):
        msg = "no, don't do that. I prefer tabs. perfect approach so far. also error"
        sigs = extract_signals(msg, "", True)
        assert len(sigs) <= 3

    def test_content_truncated_at_200(self):
        long_msg = "no, don't do " + "x" * 300
        sigs = extract_signals(long_msg, "", False)
        for s in sigs:
            assert len(s["content"]) <= 220  # "User correction: " prefix + 200
