"""Tests for cli_stream — streaming display with tool progress."""
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
    _format_tool_use,
    _handle_chunk,
    _show_error,
    stream_chunks,
)


def _make_state() -> _StreamState:
    return _StreamState(console=Console(file=io.StringIO()))


# -- _handle_chunk tests --


def test_handle_chunk_routing_prints_model():
    state = _make_state()
    _handle_chunk(state, {
        "type": "routing", "model": "kimi", "blast": 3,
    })
    output = state.console.file.getvalue()
    assert "kimi" in output


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


def test_handle_chunk_queued_prints():
    state = _make_state()
    _handle_chunk(state, {"type": "queued", "position": 2})
    output = state.console.file.getvalue()
    assert "2" in output


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


def test_handle_chunk_tool_use_prints():
    state = _make_state()
    _handle_chunk(state, {
        "type": "tool_use",
        "tool": "Read",
        "input": {"file_path": "/src/main.py"},
    })
    output = state.console.file.getvalue()
    assert "Read" in output
    assert "main.py" in output


# -- _build_display tests --


def test_build_display_spinner_when_no_content():
    state = _make_state()
    display = _build_display(state)
    assert isinstance(display, Group)
    assert len(display.renderables) == 1
    assert isinstance(display.renderables[0], Spinner)


def test_build_display_with_content():
    state = _make_state()
    state.content = "Hello"
    display = _build_display(state)
    assert len(display.renderables) == 1
    assert isinstance(display.renderables[0], Markdown)


# -- _format_tool_use tests --


def test_format_tool_use_read():
    result = _format_tool_use(
        "Read", {"file_path": "/home/user/src/main.py"},
    )
    assert "Read" in result
    assert "main.py" in result


def test_format_tool_use_bash():
    result = _format_tool_use("Bash", {"command": "git status"})
    assert "git status" in result


def test_format_tool_use_grep():
    result = _format_tool_use("Grep", {"pattern": "TODO"})
    assert "Grep" in result
    assert "TODO" in result


def test_format_tool_use_unknown():
    result = _format_tool_use("CustomTool", {})
    assert "CustomTool" in result


def test_format_tool_use_task():
    result = _format_tool_use(
        "Task", {"description": "search code"},
    )
    assert "Agent" in result
    assert "search code" in result


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


def test_stream_chunks_tool_use_displayed():
    """Tool use chunks are printed above live area."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True)
    chunks = iter([
        {"type": "routing", "model": "codex"},
        {"type": "tool_use", "tool": "Read",
         "input": {"file_path": "/src/app.py"}},
        {"type": "text", "content": "Found it."},
        {"type": "done"},
    ])
    stream_chunks(chunks, console)
    output = buf.getvalue()
    assert "codex" in output
    assert "Read" in output


def test_handle_chunk_accumulates_tool_events():
    """tool_use chunks should be stored in tool_events."""
    state = _make_state()
    _handle_chunk(state, {
        "type": "tool_use",
        "tool": "Read",
        "input": {"file_path": "/src/main.py"},
    })
    _handle_chunk(state, {
        "type": "tool_use",
        "tool": "Bash",
        "input": {"command": "git status"},
    })
    assert len(state.tool_events) == 2
    assert "Read" in state.tool_events[0]
    assert "git status" in state.tool_events[1]


def test_stream_chunks_returns_tool_events():
    """stream_chunks must return dict with tool_events."""
    console = Console(
        file=io.StringIO(), force_terminal=True,
    )
    chunks = iter([
        {"type": "tool_use", "tool": "Read",
         "input": {"file_path": "/a.py"}},
        {"type": "tool_use", "tool": "Grep",
         "input": {"pattern": "TODO"}},
        {"type": "text", "content": "Done."},
        {"type": "done"},
    ])
    result = stream_chunks(chunks, console)
    assert isinstance(result, dict)
    assert len(result["tool_events"]) == 2


def test_stream_chunks_shows_summary():
    """After streaming, a collapsed summary line is shown."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True)
    chunks = iter([
        {"type": "tool_use", "tool": "Read",
         "input": {"file_path": "/a.py"}},
        {"type": "tool_use", "tool": "Edit",
         "input": {"file_path": "/b.py"}},
        {"type": "tool_use", "tool": "Bash",
         "input": {"command": "pytest"}},
        {"type": "text", "content": "Done."},
        {"type": "done"},
    ])
    stream_chunks(chunks, console)
    output = buf.getvalue()
    assert "3 tool" in output.lower()
