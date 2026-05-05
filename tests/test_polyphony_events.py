"""Tests for Polyphony event parsing (§8 events)."""

import json
import pytest
from polyphony.events import (
    TaskEvent,
    parse_ndjson_line,
    parse_stream_json,
    classify_event,
)


class TestTaskEvent:
    def test_create(self):
        ev = TaskEvent(
            kind="message",
            data={"text": "hello"},
        )
        assert ev.kind == "message"
        assert ev.data["text"] == "hello"
        assert ev.timestamp != ""

    def test_from_dict(self):
        ev = TaskEvent.from_dict({
            "kind": "result",
            "data": {"status": "ok"},
            "timestamp": "2025-01-01T00:00:00",
        })
        assert ev.kind == "result"
        assert ev.timestamp == "2025-01-01T00:00:00"


class TestParseNdjsonLine:
    def test_valid_json(self):
        line = '{"type": "message", "content": "hello"}'
        result = parse_ndjson_line(line)
        assert result["type"] == "message"

    def test_empty_line(self):
        assert parse_ndjson_line("") is None

    def test_whitespace_line(self):
        assert parse_ndjson_line("   \n") is None

    def test_invalid_json(self):
        assert parse_ndjson_line("not json") is None

    def test_strips_whitespace(self):
        line = '  {"key": "value"}  \n'
        result = parse_ndjson_line(line)
        assert result["key"] == "value"


class TestParseStreamJson:
    def test_parses_multiple_lines(self):
        lines = [
            '{"type": "message", "text": "a"}',
            '{"type": "result", "status": "ok"}',
        ]
        events = parse_stream_json(lines)
        assert len(events) == 2
        assert events[0]["type"] == "message"
        assert events[1]["type"] == "result"

    def test_skips_invalid_lines(self):
        lines = [
            '{"type": "message"}',
            "not json",
            '{"type": "result"}',
        ]
        events = parse_stream_json(lines)
        assert len(events) == 2

    def test_empty_input(self):
        assert parse_stream_json([]) == []


class TestClassifyEvent:
    def test_result_event(self):
        ev = classify_event({"type": "result", "status": "ok"})
        assert ev.kind == "result"

    def test_message_event(self):
        ev = classify_event({"type": "message", "text": "hi"})
        assert ev.kind == "message"

    def test_error_event(self):
        ev = classify_event({"type": "error", "message": "fail"})
        assert ev.kind == "error"

    def test_unknown_event(self):
        ev = classify_event({"foo": "bar"})
        assert ev.kind == "unknown"

    def test_preserves_data(self):
        data = {"type": "result", "status": "ok", "extra": 42}
        ev = classify_event(data)
        assert ev.data == data
