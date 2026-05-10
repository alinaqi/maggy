"""Tests for ChatManager — interactive Claude sessions."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.config import CodebaseConfig, MaggyConfig


def _make_cfg(tmp_path: Path) -> MaggyConfig:
    repo = tmp_path / "my-project"
    repo.mkdir()
    return MaggyConfig(codebases=[
        CodebaseConfig(path=str(repo), key="my-project"),
    ])


class TestChatManager:
    """Test ChatManager session lifecycle."""

    def test_create_session(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        session = mgr.create_session("my-project")
        assert session.project_key == "my-project"
        assert session.status == "idle"
        assert session.working_dir == str(
            tmp_path / "my-project"
        )
        assert session.messages == []

    def test_create_session_invalid_project(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        with pytest.raises(ValueError, match="not found"):
            mgr.create_session("nonexistent")

    def test_create_with_project_path(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        # Subdirectory of configured codebase is allowed
        sub = tmp_path / "my-project" / "src"
        sub.mkdir()
        s = mgr.create_session("my-project", str(sub))
        assert s.project_key == "my-project"
        assert s.working_dir == str(sub)

    def test_create_rejects_outside_path(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        outside = tmp_path / "other-repo"
        outside.mkdir()
        with pytest.raises(ValueError, match="not inside"):
            mgr.create_session("other", str(outside))

    def test_list_sessions(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        mgr.create_session("my-project")
        mgr.create_session("my-project")
        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    def test_get_session(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        s = mgr.create_session("my-project")
        got = mgr.get_session(s.id)
        assert got is not None
        assert got.id == s.id

    def test_get_missing_session(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        assert mgr.get_session("missing") is None

    def test_build_cmd_new_session(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        s = mgr.create_session("my-project")
        cmd = mgr._build_cmd(s, "fix the bug")
        assert "claude" in cmd[0]
        assert "-p" in cmd
        assert "fix the bug" in cmd
        assert "--output-format" in cmd
        assert "--resume" not in cmd

    def test_build_cmd_resume(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        s = mgr.create_session("my-project")
        s.claude_session_id = "abc123"
        cmd = mgr._build_cmd(s, "continue working")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "abc123"

    def test_delete_session(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        s = mgr.create_session("my-project")
        assert mgr.delete_session(s.id) is True
        assert mgr.get_session(s.id) is None

    def test_delete_missing(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        assert mgr.delete_session("nope") is False

    def test_working_dir_security_bad_key(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        with pytest.raises(ValueError, match="not found"):
            mgr.create_session("hacker-repo")

    def test_working_dir_security_bad_path(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        with pytest.raises(ValueError, match="not inside"):
            mgr.create_session("x", "/etc")


class TestAutoConnect:
    """Test auto-connect to active projects."""

    def test_auto_connect_creates_sessions(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        repo = tmp_path / "my-project"
        active = [
            {"project": "my-project", "project_path": str(repo)},
        ]
        result = mgr.auto_connect(active)
        assert len(result) == 1
        assert result[0].project_key == "my-project"

    def test_auto_connect_deduplicates(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        repo = tmp_path / "my-project"
        active = [
            {"project": "my-project", "project_path": str(repo)},
            {"project": "my-project", "project_path": str(repo)},
        ]
        result = mgr.auto_connect(active)
        assert len(result) == 1

    def test_auto_connect_multiple_projects(self, tmp_path):
        from maggy.services.chat import ChatManager
        r1 = tmp_path / "proj-a"
        r2 = tmp_path / "proj-b"
        r1.mkdir()
        r2.mkdir()
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path=str(r1), key="proj-a"),
            CodebaseConfig(path=str(r2), key="proj-b"),
        ])
        mgr = ChatManager(cfg)
        active = [
            {"project": "proj-a", "project_path": str(r1)},
            {"project": "proj-b", "project_path": str(r2)},
        ]
        result = mgr.auto_connect(active)
        assert len(result) == 2
        keys = {s.project_key for s in result}
        assert keys == {"proj-a", "proj-b"}

    def test_auto_connect_skips_empty(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        repo = tmp_path / "my-project"
        active = [
            {"project": "", "project_path": ""},
            {"project": "my-project", "project_path": str(repo)},
        ]
        result = mgr.auto_connect(active)
        assert len(result) == 1

    def test_find_by_project(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        s = mgr.create_session("my-project")
        found = mgr.find_by_project("my-project")
        assert found is not None
        assert found.id == s.id

    def test_find_by_project_missing(self, tmp_path):
        from maggy.services.chat import ChatManager
        cfg = _make_cfg(tmp_path)
        mgr = ChatManager(cfg)
        assert mgr.find_by_project("nope") is None
