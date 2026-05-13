"""Tests for chat streaming JSON parser and usage extraction."""

from __future__ import annotations

import json

from maggy.services.chat_stream import parse_chunks


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
    chunks = parse_chunks(data, session)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["type"] == "result"
    assert chunk["cost_usd"] == 0.05
    assert chunk["input_tokens"] == 1500
    assert chunk["output_tokens"] == 800


def test_parse_result_without_usage():
    session = _FakeSession()
    data = json.dumps({"type": "result", "result": "Done"})
    chunks = parse_chunks(data, session)
    assert len(chunks) == 1
    assert chunks[0]["type"] == "result"
    assert "cost_usd" not in chunks[0]


def test_parse_assistant_text():
    session = _FakeSession()
    data = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hello"}]},
    })
    chunks = parse_chunks(data, session)
    assert len(chunks) == 1
    assert chunks[0]["type"] == "text"
    assert chunks[0]["content"] == "Hello"


def test_parse_captures_session_id():
    session = _FakeSession()
    data = json.dumps({"session_id": "abc123", "type": "system"})
    parse_chunks(data, session)
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
    chunks = parse_chunks(data, session)
    assert chunks[0]["cost_usd"] == 0.0
    assert chunks[0]["input_tokens"] == 0
    assert chunks[0]["output_tokens"] == 0


def test_parse_invalid_json():
    session = _FakeSession()
    chunks = parse_chunks("not json {{", session)
    assert len(chunks) == 1
    assert chunks[0]["type"] == "text"


# -- tool_use extraction --


def test_parse_tool_use_extracted():
    """tool_use blocks yield tool_use chunks."""
    session = _FakeSession()
    data = json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/src/main.py"}},
        ]},
    })
    chunks = parse_chunks(data, session)
    assert len(chunks) == 1
    assert chunks[0]["type"] == "tool_use"
    assert chunks[0]["tool"] == "Read"
    assert chunks[0]["input"]["file_path"] == "/src/main.py"


def test_parse_mixed_text_and_tool_use():
    """Both text and tool_use in one message."""
    session = _FakeSession()
    data = json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "text", "text": "Let me read it."},
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "git status"}},
        ]},
    })
    chunks = parse_chunks(data, session)
    assert len(chunks) == 2
    assert chunks[0]["type"] == "text"
    assert chunks[0]["content"] == "Let me read it."
    assert chunks[1]["type"] == "tool_use"
    assert chunks[1]["tool"] == "Bash"


def test_parse_unknown_type_returns_empty():
    """Unknown message types return empty list."""
    session = _FakeSession()
    data = json.dumps({"type": "system", "data": "init"})
    chunks = parse_chunks(data, session)
    assert chunks == []
