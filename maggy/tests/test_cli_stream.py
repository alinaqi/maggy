"""Tests for cli_stream — streaming display with model label."""
from __future__ import annotations

import io
from unittest.mock import patch

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

from maggy.cli_stream import (
    _StreamState,
    _build_display,
    _handle_chunk,
    _show_error,
    stream_chunks,
)


def _make_state() -> _StreamState:
    return _StreamState(console=Console(file=io.StringIO()))


# -- _handle_chunk tests --


def test_handle_chunk_routing_sets_label():
    state = _make_state()
    _handle_chunk(state, {
        "type": "routing", "model": "kimi", "blast": 3,
    })
    assert "kimi" in state.model_label


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


def test_handle_chunk_unknown_type_ignored():
    state = _make_state()
    assert _handle_chunk(state, {"type": "mystery"})
    assert state.content == ""
    assert state.model_label == ""


# -- _build_display tests --


def test_build_display_spinner_when_no_content():
    state = _make_state()
    display = _build_display(state)
    assert isinstance(display, Group)
    assert len(display.renderables) == 1
    assert isinstance(display.renderables[0], Spinner)


def test_build_display_with_model_and_content():
    state = _make_state()
    state.model_label = "kimi"
    state.content = "Hello"
    display = _build_display(state)
    assert len(display.renderables) == 2
    assert isinstance(display.renderables[0], Text)
    assert isinstance(display.renderables[1], Markdown)


def test_build_display_model_only():
    state = _make_state()
    state.model_label = "claude"
    display = _build_display(state)
    # model label + spinner
    assert len(display.renderables) == 2
    assert isinstance(display.renderables[0], Text)
    assert isinstance(display.renderables[1], Spinner)


# -- __rich__ protocol --


def test_stream_state_rich_protocol():
    state = _make_state()
    state.content = "test"
    display = state.__rich__()
    assert isinstance(display, Group)


# -- _show_error tests --


def test_show_error_noop_when_empty():
    state = _make_state()
    _show_error(state)
    assert state.console.file.getvalue() == ""


def test_show_error_prints_message():
    state = _make_state()
    state.error = "something broke"
    _show_error(state)
    assert "something broke" in state.console.file.getvalue()


def test_show_error_quota_triggers_guide():
    state = _make_state()
    state.error = "rate_limit_exceeded: quota hit"
    with patch(
        "maggy.services.account_guide.render_switch_guide",
    ) as mock_guide:
        _show_error(state)
    mock_guide.assert_called_once_with("anthropic")


# -- stream_chunks integration --


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


def test_stream_chunks_empty_iterator():
    """Empty chunk iterator doesn't crash."""
    console = Console(
        file=io.StringIO(), force_terminal=True,
    )
    stream_chunks(iter([]), console)
