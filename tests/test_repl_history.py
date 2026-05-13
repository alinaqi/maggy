"""Tests for REPL command history with arrow keys."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from maggy.cli_chat import _read_input


def test_read_input_returns_stripped():
    """User input is stripped of whitespace."""
    with patch("builtins.input", return_value="  hello  "):
        result = _read_input("> ")
    assert result == "hello"


def test_read_input_eof_returns_none():
    """Ctrl-D returns None."""
    with patch("builtins.input", side_effect=EOFError):
        result = _read_input("> ")
    assert result is None


def test_read_input_interrupt_returns_none():
    """Ctrl-C returns None."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = _read_input("> ")
    assert result is None
