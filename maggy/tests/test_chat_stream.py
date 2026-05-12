"""Tests for chat streaming JSON parser and usage extraction."""

from __future__ import annotations

import json

from maggy.services.chat_stream import parse_chunk


class _FakeSession:
    def __init__(self):
        self.claude_session_id = ""


def test_parse_result_extracts_usage():
    session = _FakeSession()
    data = json.dumps({
        "type": "result",
        "result": "Done",
        "cost_usd": 0.05,
        "usage": {"input_tokens": 1500, "output_tokens": 800},
    })
    chunk = parse_chunk(data, session)
    assert chunk["type"] == "result"
    assert chunk["content"] == "Done"
    assert chunk["cost_usd"] == 0.05
    assert chunk["input_tokens"] == 1500
    assert chunk["output_tokens"] == 800


def test_parse_result_without_usage():
    session = _FakeSession()
    data = json.dumps({"type": "result", "result": "Done"})
    chunk = parse_chunk(data, session)
    assert chunk["type"] == "result"
    assert chunk["content"] == "Done"
    assert "cost_usd" not in chunk


def test_parse_assistant_text():
    session = _FakeSession()
    data = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hello"}]},
    })
    chunk = parse_chunk(data, session)
    assert chunk["type"] == "text"
    assert chunk["content"] == "Hello"


def test_parse_captures_session_id():
    session = _FakeSession()
    data = json.dumps({"session_id": "abc123", "type": "system"})
    parse_chunk(data, session)
    assert session.claude_session_id == "abc123"


def test_parse_result_zero_cost_preserved():
    """cost_usd=0.0 must appear in chunk, not be dropped."""
    session = _FakeSession()
    data = json.dumps({
        "type": "result",
        "result": "Done",
        "cost_usd": 0.0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    })
    chunk = parse_chunk(data, session)
    assert chunk["cost_usd"] == 0.0
    assert chunk["input_tokens"] == 0
    assert chunk["output_tokens"] == 0


def test_parse_invalid_json():
    session = _FakeSession()
    chunk = parse_chunk("not json {{", session)
    assert chunk["type"] == "text"
