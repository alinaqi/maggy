"""Regression tests for session lifecycle — prevents thinking block bug.

The root cause: _enrich_and_format() called resolve_claude_session_id()
which read ~/.claude/history.jsonl, found stale session IDs, and injected
them for --resume. Claude API rejected these with "Invalid signature in
thinking block". The fix removed resolve_claude_session_id() from
enrichment entirely. These tests ensure it never comes back.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maggy.config import CodebaseConfig, MaggyConfig
from maggy.services.chat_models import ChatMessage, ChatSession
from maggy.services.chat_stream import build_cmd, _classify_error
from maggy.services.session_store import SessionStore


def _make_session(
    sid: str = "test-001",
    claude_id: str = "",
    working_dir: str = "/tmp/test-project",
) -> ChatSession:
    return ChatSession(
        id=sid,
        claude_session_id=claude_id,
        project_key="test-project",
        working_dir=working_dir,
        repo_dir=working_dir,
        isolation="none",
        label="main",
    )


class TestBuildCmdResumeGuard:
    """build_cmd must never add --resume without a valid session ID."""

    def test_no_resume_when_id_empty(self):
        session = _make_session(claude_id="")
        cmd = build_cmd(session, "hello")
        assert "--resume" not in cmd

    def test_no_resume_when_id_whitespace(self):
        session = _make_session(claude_id="   ")
        cmd = build_cmd(session, "hello")
        assert "--resume" not in cmd

    def test_resume_only_with_valid_id(self):
        session = _make_session(claude_id="valid-abc123")
        cmd = build_cmd(session, "hello")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "valid-abc123"

    def test_system_prompt_always_present(self):
        session = _make_session()
        cmd = build_cmd(session, "hello")
        assert "--append-system-prompt" in cmd


class TestEnrichAndFormat:
    """_enrich_and_format must never inject stale session IDs."""

    def test_never_sets_claude_session_id(self):
        from maggy.api.routes_chat_sessions import _enrich_and_format
        session = _make_session(claude_id="")
        with patch(
            "maggy.services.chat_context.build_project_context",
            return_value="some context",
        ):
            result = _enrich_and_format(session, None, [])
        assert session.claude_session_id == ""
        assert result["has_resume_id"] is False

    def test_preserves_existing_valid_id(self):
        from maggy.api.routes_chat_sessions import _enrich_and_format
        session = _make_session(claude_id="legit-from-stream")
        with patch(
            "maggy.services.chat_context.build_project_context",
            return_value="",
        ):
            result = _enrich_and_format(session, None, [])
        assert session.claude_session_id == "legit-from-stream"
        assert result["has_resume_id"] is True

    def test_does_not_call_resolve(self):
        from maggy.api.routes_chat_sessions import _enrich_and_format
        session = _make_session(claude_id="")
        with patch(
            "maggy.services.chat_context.build_project_context",
            return_value="",
        ):
            _enrich_and_format(session, None, [])
        assert session.claude_session_id == ""


class TestSessionStoreRoundTrip:
    """SQLite round-trip must preserve cleared session IDs."""

    def test_empty_id_survives_round_trip(self, tmp_path: Path):
        db = tmp_path / "sessions.db"
        store = SessionStore(db)
        store.save_session(
            "s1", "proj", "/tmp/proj", "",
            repo_dir="/tmp/proj", isolation="none", label="main",
        )
        rows = store.load_sessions()
        assert len(rows) == 1
        assert rows[0]["claude_session_id"] == ""

    def test_clear_id_persists(self, tmp_path: Path):
        db = tmp_path / "sessions.db"
        store = SessionStore(db)
        store.save_session(
            "s1", "proj", "/tmp/proj", "old-stale-id",
        )
        store.update_claude_id("s1", "")
        rows = store.load_sessions()
        assert rows[0]["claude_session_id"] == ""

    def test_clear_survives_reopen(self, tmp_path: Path):
        db = tmp_path / "sessions.db"
        store1 = SessionStore(db)
        store1.save_session("s1", "proj", "/tmp/proj", "stale-id")
        store1.update_claude_id("s1", "")
        store2 = SessionStore(db)
        rows = store2.load_sessions()
        assert rows[0]["claude_session_id"] == ""

    def test_mark_cleared_sets_flag_and_empties_id(self, tmp_path: Path):
        db = tmp_path / "sessions.db"
        store = SessionStore(db)
        store.save_session("s1", "proj", "/tmp/proj", "doomed-id")
        store.mark_session_cleared("s1")
        rows = store.load_sessions()
        assert rows[0]["claude_session_id"] == ""
        assert rows[0].get("session_cleared") in ("1", 1)


class TestRestoreSessionsNeverAutoResolve:
    """ChatManager._restore_sessions must not auto-resolve stale IDs."""

    def test_restore_keeps_empty_id(self, tmp_path: Path):
        from maggy.services.chat import ChatManager
        db = tmp_path / "sessions.db"
        store = SessionStore(db)
        store.save_session(
            "s1", "proj", str(tmp_path), "",
            repo_dir=str(tmp_path), isolation="none", label="test",
        )
        repo = tmp_path / "proj"
        repo.mkdir(exist_ok=True)
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path=str(repo), key="proj"),
        ])
        mgr = ChatManager(cfg, store=store)
        session = mgr.get_session("s1")
        assert session is not None
        assert session.claude_session_id == ""

    def test_restore_keeps_valid_id(self, tmp_path: Path):
        from maggy.services.chat import ChatManager
        db = tmp_path / "sessions.db"
        store = SessionStore(db)
        store.save_session(
            "s1", "proj", str(tmp_path), "valid-id-from-stream",
            repo_dir=str(tmp_path), isolation="none", label="test",
        )
        repo = tmp_path / "proj"
        repo.mkdir(exist_ok=True)
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path=str(repo), key="proj"),
        ])
        mgr = ChatManager(cfg, store=store)
        session = mgr.get_session("s1")
        assert session.claude_session_id == "valid-id-from-stream"


class TestErrorClassification:
    """Error classification must catch thinking block errors."""

    def test_thinking_block_classified_as_session(self):
        chunk = {
            "type": "error",
            "content": "400 messages.3.content.0: Invalid signature in thinking block",
        }
        assert _classify_error(chunk) == "session"

    def test_session_not_found_classified(self):
        chunk = {"type": "error", "content": "Session not found"}
        assert _classify_error(chunk) == "session"

    def test_overload_classified(self):
        chunk = {"type": "error", "content": "API overloaded, try later"}
        assert _classify_error(chunk) == "overload"

    def test_context_too_long_classified(self):
        chunk = {"type": "error", "content": "context length exceeded"}
        assert _classify_error(chunk) == "context"

    def test_normal_text_not_classified(self):
        chunk = {"type": "text", "content": "Hello, how can I help?"}
        assert _classify_error(chunk) is None


class TestPreloadDoesNotInjectStaleIds:
    """Preload/auto-connect must never set claude_session_id from history."""

    def test_preload_new_session_has_no_resume_id(self, tmp_path: Path):
        from maggy.services.chat import ChatManager
        repo = tmp_path / "my-project"
        repo.mkdir()
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path=str(repo), key="my-project"),
        ])
        mgr = ChatManager(cfg)
        session = mgr.create_session("my-project")
        assert session.claude_session_id == ""
        cmd = build_cmd(session, "test")
        assert "--resume" not in cmd

    def test_auto_connect_sessions_have_no_resume_id(self, tmp_path: Path):
        from maggy.services.chat import ChatManager
        repo = tmp_path / "proj-a"
        repo.mkdir()
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path=str(repo), key="proj-a"),
        ])
        mgr = ChatManager(cfg)
        active = [{"project": "proj-a", "project_path": str(repo)}]
        sessions = mgr.auto_connect(active)
        assert len(sessions) == 1
        assert sessions[0].claude_session_id == ""
