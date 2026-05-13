"""Tests for stale Claude session recovery."""
from __future__ import annotations

import pytest

from maggy.services.chat_stream import _is_stale_error


def test_detects_stale_session_error():
    chunk = {"type": "text", "content": "Error: Task chat-abc not found"}
    assert _is_stale_error(chunk) is True


def test_ignores_normal_text():
    chunk = {"type": "text", "content": "File not found in repo"}
    assert _is_stale_error(chunk) is False


def test_ignores_non_text_chunks():
    chunk = {"type": "tool_use", "content": "Error: not found"}
    assert _is_stale_error(chunk) is False


def test_ignores_empty_chunk():
    assert _is_stale_error({}) is False


def test_detects_session_not_found():
    chunk = {"type": "text", "content": "Error: Session xyz not found"}
    assert _is_stale_error(chunk) is True
