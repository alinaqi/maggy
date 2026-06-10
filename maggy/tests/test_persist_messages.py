"""Tests for message persistence — prevents compaction data loss."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from maggy.config import CodebaseConfig, MaggyConfig
from maggy.services.chat_models import ChatMessage, ChatSession


def _make_cfg(tmp_path: Path) -> MaggyConfig:
    return MaggyConfig(
        codebases=[CodebaseConfig(key="test", path=str(tmp_path))],
    )


def _make_store(tmp_path: Path):
    from maggy.services.session_store import SessionStore
    return SessionStore(tmp_path / "test.db")


class TestPersistAfterSend:
    def test_saves_user_and_assistant(self, tmp_path):
        from maggy.services.chat import ChatManager
        store = _make_store(tmp_path)
        mgr = ChatManager(_make_cfg(tmp_path), store=store)
        s = mgr.create_session("test", str(tmp_path))
        s.messages.append(ChatMessage(role="user", content="hello"))
        s.messages.append(ChatMessage(role="assistant", content="hi"))
        mgr._persist_after_send(s)
        msgs = store.load_messages(s.id)
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant"]

    def test_persists_after_compaction(self, tmp_path):
        from maggy.services.chat import ChatManager
        store = _make_store(tmp_path)
        mgr = ChatManager(_make_cfg(tmp_path), store=store)
        s = mgr.create_session("test", str(tmp_path))
        for i in range(20):
            s.messages.append(ChatMessage(role="user", content=f"q{i}"))
            s.messages.append(ChatMessage(role="assistant", content=f"a{i}"))
        mgr._persist_after_send(s)
        assert len(store.load_messages(s.id)) == 40

        from maggy.services.context_compactor import compact_messages
        s.messages = compact_messages(s.messages)
        s._persisted_idx = 0

        s.messages.append(ChatMessage(role="user", content="new question"))
        s.messages.append(ChatMessage(role="assistant", content="new answer"))
        mgr._persist_after_send(s)

        msgs = store.load_messages(s.id)
        last_two = msgs[-2:]
        assert last_two[0]["role"] == "user"
        assert last_two[0]["content"] == "new question"
        assert last_two[1]["role"] == "assistant"

    def test_no_double_persist(self, tmp_path):
        from maggy.services.chat import ChatManager
        store = _make_store(tmp_path)
        mgr = ChatManager(_make_cfg(tmp_path), store=store)
        s = mgr.create_session("test", str(tmp_path))
        s.messages.append(ChatMessage(role="user", content="hello"))
        s.messages.append(ChatMessage(role="assistant", content="hi"))
        mgr._persist_after_send(s)
        mgr._persist_after_send(s)
        msgs = store.load_messages(s.id)
        assert len(msgs) == 2

    def test_restored_session_persists_new(self, tmp_path):
        from maggy.services.chat import ChatManager
        store = _make_store(tmp_path)
        mgr = ChatManager(_make_cfg(tmp_path), store=store)
        s = mgr.create_session("test", str(tmp_path))
        s.messages.append(ChatMessage(role="user", content="old"))
        s.messages.append(ChatMessage(role="assistant", content="old reply"))
        mgr._persist_after_send(s)

        mgr2 = ChatManager(_make_cfg(tmp_path), store=store)
        s2 = mgr2.get_session(s.id)
        assert s2 is not None
        assert len(s2.messages) == 2
        s2.messages.append(ChatMessage(role="user", content="new"))
        s2.messages.append(ChatMessage(role="assistant", content="new reply"))
        mgr2._persist_after_send(s2)
        msgs = store.load_messages(s.id)
        assert len(msgs) == 4
        assert msgs[2]["content"] == "new"
        assert msgs[2]["role"] == "user"
