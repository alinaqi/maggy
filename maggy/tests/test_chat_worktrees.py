"""Worktree isolation for parallel chats — tested against a real git repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maggy.config import MaggyConfig
from maggy.services.chat import ChatManager


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path):
    """A real git repo with one commit on its main branch."""
    r = tmp_path / "proj"
    r.mkdir()
    _git(["init", "-q"], r)
    _git(["config", "user.email", "t@t.co"], r)
    _git(["config", "user.name", "t"], r)
    (r / "README.md").write_text("hi\n")
    _git(["add", "."], r)
    _git(["commit", "-qm", "init"], r)
    return r


@pytest.fixture()
def manager(tmp_path):
    return ChatManager(MaggyConfig(), worktree_base=tmp_path / "wt")


class TestIsolation:
    def test_first_chat_uses_main_tree(self, manager, repo):
        s = manager.create_session("proj", str(repo))
        assert s.isolation == "none"
        assert s.working_dir == str(repo)

    def test_isolated_chat_gets_worktree_and_branch(self, manager, repo):
        s = manager.create_session("proj", str(repo), isolated=True)
        assert s.isolation == "worktree"
        assert s.working_dir != str(repo)
        assert Path(s.working_dir).is_dir()           # worktree exists on disk
        assert s.repo_dir == str(repo)                # linked back to the repo
        branches = subprocess.run(["git", "-C", str(repo), "branch", "--format=%(refname:short)"],
                                  capture_output=True, text=True).stdout.split()
        assert f"maggy/{s.id}" in branches            # its own branch

    def test_second_chat_auto_isolates(self, manager, repo):
        first = manager.create_session("proj", str(repo))
        second = manager.create_session("proj", str(repo))  # no isolated flag
        assert first.isolation == "none"
        assert second.isolation == "worktree"          # auto-isolated to avoid collision
        assert second.working_dir != first.working_dir

    def test_parallel_chats_are_on_separate_branches(self, manager, repo):
        manager.create_session("proj", str(repo))
        a = manager.create_session("proj", str(repo), isolated=True)
        b = manager.create_session("proj", str(repo), isolated=True)
        assert a.working_dir != b.working_dir
        assert a.label != b.label                      # distinct branches

    def test_delete_removes_worktree(self, manager, repo):
        s = manager.create_session("proj", str(repo), isolated=True)
        wt = Path(s.working_dir)
        assert wt.is_dir()
        assert manager.delete_session(s.id) is True
        assert not wt.is_dir()                          # worktree gone

    def test_non_git_dir_falls_back_to_main(self, manager, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        s = manager.create_session("plain", str(plain), isolated=True)
        assert s.isolation == "none"                    # can't worktree a non-repo
        assert s.working_dir == str(plain)


class TestApiEndToEnd:
    """Full path through the HTTP API: create isolated → worktree → delete."""

    def test_create_isolated_then_delete(self, repo, tmp_path):
        from fastapi.testclient import TestClient
        from maggy.main import create_app
        app = create_app()
        app.state.cfg = MaggyConfig()
        app.state.chat = ChatManager(MaggyConfig(), worktree_base=tmp_path / "apiwt")
        client = TestClient(app)

        r = client.post("/api/chat/sessions",
                        json={"project_key": "proj", "project_path": str(repo), "isolated": True})
        assert r.status_code == 200
        body = r.json()
        assert body["isolation"] == "worktree"
        assert body["label"].startswith("maggy/")
        from pathlib import Path
        assert Path(body["working_dir"]).is_dir()       # worktree created
        assert Path(body["working_dir"]) != repo

        wt = body["working_dir"]
        assert client.delete(f"/api/chat/sessions/{body['id']}").status_code == 200
        assert not Path(wt).is_dir()                     # worktree cleaned up
