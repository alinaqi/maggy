"""Tests for session store — SQLite session persistence."""
from __future__ import annotations

from pathlib import Path

import pytest

from maggy.services.session_store import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.db")


def test_save_and_load(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "claude-abc")
    sessions = store.load_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "s1"
    assert sessions[0]["project_key"] == "proj"
    assert sessions[0]["claude_session_id"] == "claude-abc"


def test_update_claude_session_id(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "")
    store.update_claude_id("s1", "new-id")
    sessions = store.load_sessions()
    assert sessions[0]["claude_session_id"] == "new-id"


def test_save_and_load_messages(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "")
    store.append_message("s1", "user", "hello")
    store.append_message("s1", "assistant", "hi there")
    msgs = store.load_messages("s1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "hi there"


def test_delete_session(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "")
    store.append_message("s1", "user", "hello")
    store.delete_session("s1")
    assert store.load_sessions() == []
    assert store.load_messages("s1") == []


def test_no_duplicate_sessions(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "")
    store.save_session("s1", "proj", "/tmp/proj", "updated")
    sessions = store.load_sessions()
    assert len(sessions) == 1
    assert sessions[0]["claude_session_id"] == "updated"


def test_multiple_sessions(store: SessionStore):
    store.save_session("s1", "p1", "/tmp/p1", "")
    store.save_session("s2", "p2", "/tmp/p2", "")
    sessions = store.load_sessions()
    assert len(sessions) == 2


def test_messages_ordered(store: SessionStore):
    store.save_session("s1", "proj", "/tmp/proj", "")
    for i in range(5):
        store.append_message("s1", "user", f"msg{i}")
    msgs = store.load_messages("s1")
    assert [m["content"] for m in msgs] == [
        "msg0", "msg1", "msg2", "msg3", "msg4",
    ]
