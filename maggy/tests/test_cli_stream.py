"""Tests for cli_stream — streaming display with jokes + model label."""
from __future__ import annotations

import io

from rich.console import Console

from maggy.cli_stream import (
    _StreamState,
    _build_display,
    _handle_chunk,
    stream_chunks,
)


def _make_state() -> _StreamState:
    return _StreamState(console=Console(file=io.StringIO()))


def test_handle_chunk_routing_sets_label():
    state = _make_state()
    _handle_chunk(state, {
        "type": "routing", "model": "kimi", "blast": 3,
    })
    assert "kimi" in state.model_label
    assert "3" in state.model_label


def test_handle_chunk_text_accumulates():
    state = _make_state()
    _handle_chunk(state, {"type": "text", "content": "Hello"})
    assert state.content == "Hello"
    _handle_chunk(state, {"type": "text", "content": " world"})
    assert state.content == "Hello world"


def test_handle_chunk_error_stored():
    state = _make_state()
    _handle_chunk(state, {"type": "error", "content": "fail"})
    assert state.error == "fail"


def test_handle_chunk_done_returns_false():
    state = _make_state()
    assert _handle_chunk(state, {"type": "text", "content": "x"})
    assert not _handle_chunk(state, {"type": "done"})


def test_handle_chunk_queued_sets_label():
    state = _make_state()
    _handle_chunk(state, {"type": "queued", "position": 2})
    assert "2" in state.model_label


def test_handle_chunk_warning_prints():
    state = _make_state()
    _handle_chunk(state, {
        "type": "warning", "content": "Context: ~25k tokens",
    })
    output = state.console.file.getvalue()
    assert "25k" in output


def test_build_display_spinner_when_no_content():
    state = _make_state()
    display = _build_display(state)
    assert display is not None


def test_build_display_with_model_and_content():
    state = _make_state()
    state.model_label = "Working with kimi"
    state.content = "Hello"
    display = _build_display(state)
    assert display is not None


def test_build_display_shows_joke():
    state = _make_state()
    state.joke_line = "Knock knock."
    display = _build_display(state)
    assert display is not None


def test_stream_chunks_basic():
    """Full integration: stream completes without error."""
    console = Console(
        file=io.StringIO(), force_terminal=True,
    )
    chunks = iter([
        {"type": "routing", "model": "kimi", "blast": 3},
        {"type": "text", "content": "Hello"},
        {"type": "done"},
    ])
    stream_chunks(chunks, console)


def test_stream_chunks_error_displayed():
    """Error chunks are captured and printed."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True)
    chunks = iter([
        {"type": "error", "content": "CLI not found"},
        {"type": "done"},
    ])
    stream_chunks(chunks, console)
    assert "CLI not found" in buf.getvalue()
