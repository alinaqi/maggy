"""Tests for background task auto-finish without Enter press."""
from __future__ import annotations

import threading
import time
from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from maggy.cli_bg_task import TaskState
from maggy.cli_chat import _bg_loop, _finish_bg
from maggy.cli_repl_cmds import SessionState


def _console() -> Console:
    return Console(file=StringIO(), force_terminal=False, width=120)


def _quick_task() -> TaskState:
    """Task that completes in 0.1s."""
    bg = TaskState()
    bg.status = "running"

    def finish():
        time.sleep(0.1)
        with bg.lock:
            bg.status = "done"
            bg.content = "the answer"

    threading.Thread(target=finish, daemon=True).start()
    return bg


def _session() -> SessionState:
    return SessionState(session_id="s1", working_dir="/tmp")


@patch("maggy.cli_chat.console")
@patch("maggy.cli_chat.select")
def test_auto_finishes_without_enter(mock_sel, mock_con):
    """Loop exits and shows result when task completes."""
    mock_con.print = MagicMock()
    mock_sel.select.return_value = ([], [], [])
    bg = _quick_task()
    state = _session()
    _bg_loop(MagicMock(), state, bg)
    assert bg.status == "done"


@patch("maggy.cli_chat.console")
@patch("maggy.cli_chat.select")
def test_result_displayed_on_finish(mock_sel, mock_con):
    """Content from bg task renders as markdown."""
    printed: list = []
    mock_con.print = lambda *a, **kw: printed.append(a[0])
    mock_sel.select.return_value = ([], [], [])
    bg = _quick_task()
    state = _session()
    _bg_loop(MagicMock(), state, bg)
    md_items = [p for p in printed if hasattr(p, "markup")]
    assert any("the answer" in p.markup for p in md_items)


@patch("maggy.cli_chat.console")
@patch("maggy.cli_chat.select")
def test_error_displayed_on_finish(mock_sel, mock_con):
    """Error from bg task is shown."""
    buf = StringIO()
    mock_con.print = lambda *a, **kw: buf.write(str(a[0]))
    mock_sel.select.return_value = ([], [], [])
    bg = TaskState()
    bg.status = "running"

    def finish():
        time.sleep(0.1)
        with bg.lock:
            bg.status = "done"
            bg.error = "timeout"

    threading.Thread(target=finish, daemon=True).start()
    state = _session()
    _bg_loop(MagicMock(), state, bg)
    assert "timeout" in buf.getvalue()


@patch("maggy.cli_chat.console")
@patch("maggy.cli_chat.select")
def test_dispatch_during_bg(mock_sel, mock_con):
    """Commands dispatched when stdin has data."""
    mock_con.print = MagicMock()
    call_count = {"n": 0}

    def fake_select(*_a, **_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ([True], [], [])
        return ([], [], [])

    mock_sel.select = fake_select
    bg = _quick_task()
    state = _session()
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.readline.return_value = "/status\n"
        _bg_loop(MagicMock(), state, bg)
    assert bg.status == "done"
