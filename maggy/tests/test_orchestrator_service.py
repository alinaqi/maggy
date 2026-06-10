"""Tests for OrchestratorService — team lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.orchestrator.isolation import IsolationLevel
from maggy.orchestrator.models import Task
from maggy.services.orchestrator import (
    OrchestratorService,
    TeamSession,
    _resolve_isolation,
)

_MOD = "maggy.services.orchestrator"


def _make_service(**overrides) -> OrchestratorService:
    cfg = MagicMock()
    cfg.orchestrator.max_concurrent = 3
    cfg.orchestrator.workspace_root = "/tmp/maggy-ws"
    cfg.orchestrator.container_timeout = 600
    return OrchestratorService(cfg=cfg, **overrides)


def _make_task(title: str = "Add auth") -> Task:
    return Task(title=title, source="test", source_ref="t1")


class TestSpawnTeam:
    @pytest.mark.asyncio
    async def test_creates_team_session(self):
        svc = _make_service()
        subtasks = [_make_task("sub-1"), _make_task("sub-2")]
        with patch.object(svc, "_run_team", new_callable=AsyncMock):
            session = await svc.spawn_team("parent-1", subtasks)
        assert isinstance(session, TeamSession)
        assert session.task_id == "parent-1"
        assert len(session.subtasks) == 2

    @pytest.mark.asyncio
    async def test_lists_active_teams(self):
        svc = _make_service()
        subtasks = [_make_task()]
        with patch.object(svc, "_run_team", new_callable=AsyncMock):
            await svc.spawn_team("t1", subtasks)
        teams = svc.list_teams()
        assert len(teams) == 1


class TestRunOne:
    @pytest.mark.asyncio
    async def test_container_lifecycle(self):
        svc = _make_service()
        subtask = _make_task()
        session = TeamSession(
            team_id="tm1", task_id="p1", subtasks=[subtask],
        )
        with patch(f"{_MOD}.async_create_container", new_callable=AsyncMock, return_value="cid1"), \
             patch(f"{_MOD}.async_start_container", new_callable=AsyncMock), \
             patch(f"{_MOD}.async_wait_container", new_callable=AsyncMock, return_value=0), \
             patch(f"{_MOD}.container_logs", return_value="done"), \
             patch(f"{_MOD}.async_remove_container", new_callable=AsyncMock), \
             patch(f"{_MOD}.route_subtask", return_value=MagicMock(id="rs1", agent="claude")):
            result = await svc._run_one(subtask, session)
        assert result.status == "succeeded"

    @pytest.mark.asyncio
    async def test_container_failure(self):
        svc = _make_service()
        subtask = _make_task()
        session = TeamSession(
            team_id="tm1", task_id="p1", subtasks=[subtask],
        )
        with patch(f"{_MOD}.async_create_container", new_callable=AsyncMock, side_effect=RuntimeError("no docker")):
            result = await svc._run_one(subtask, session)
        assert result.status == "failed"


class TestCancelTeam:
    @pytest.mark.asyncio
    async def test_cancel_sets_status(self):
        svc = _make_service()
        subtasks = [_make_task()]
        with patch.object(svc, "_run_team", new_callable=AsyncMock):
            session = await svc.spawn_team("t1", subtasks)
        await svc.cancel_team(session.team_id)
        assert svc.get_team(session.team_id).status == "cancelled"


class TestRouteSubtaskImage:
    def test_default_image_matches_built_worker(self):
        from maggy.services.orchestrator import route_subtask
        spec = route_subtask(_make_task())
        assert spec.image == "polyphony-worker:latest"

    def test_honors_explicit_image(self):
        from maggy.services.orchestrator import route_subtask
        spec = route_subtask(_make_task(), image="custom:tag")
        assert spec.image == "custom:tag"

    @pytest.mark.asyncio
    async def test_run_one_uses_configured_image(self):
        svc = _make_service()
        svc._cfg.orchestrator.image = "from-config:latest"
        svc._isolation = IsolationLevel.CONTAINER
        subtask = _make_task()
        session = TeamSession(team_id="tm1", task_id="p1", subtasks=[subtask])
        captured = {}

        async def _capture(spec):
            captured["image"] = spec.image
            return "cid1"

        with patch(f"{_MOD}.async_create_container", new=_capture), \
             patch(f"{_MOD}.async_start_container", new_callable=AsyncMock), \
             patch(f"{_MOD}.async_wait_container", new_callable=AsyncMock, return_value=0), \
             patch(f"{_MOD}.container_logs", return_value="done"), \
             patch(f"{_MOD}.async_remove_container", new_callable=AsyncMock):
            await svc._run_one(subtask, session)
        assert captured["image"] == "from-config:latest"


class TestResolveIsolation:
    def test_explicit_levels(self):
        assert _resolve_isolation("docker") == IsolationLevel.CONTAINER
        assert _resolve_isolation("worktree") == IsolationLevel.WORKTREE
        assert _resolve_isolation("local") == IsolationLevel.LOCK_ONLY

    def test_auto_probes_host(self):
        with patch(f"{_MOD}.detect_capabilities", return_value=IsolationLevel.WORKTREE):
            assert _resolve_isolation("auto") == IsolationLevel.WORKTREE

    def test_unknown_falls_back_to_auto(self):
        with patch(f"{_MOD}.detect_capabilities", return_value=IsolationLevel.LOCK_ONLY):
            assert _resolve_isolation("bogus") == IsolationLevel.LOCK_ONLY


class TestProvision:
    def test_no_repo_returns_empty(self):
        svc = _make_service()
        ws, isolated = svc._provision(IsolationLevel.WORKTREE, None, "s1")
        assert ws == ""
        assert isolated is False

    def test_worktree_path_is_isolated(self):
        svc = _make_service()
        with patch(f"{_MOD}.provision_workspace", return_value="/ws/worktrees/s1"):
            ws, isolated = svc._provision(IsolationLevel.WORKTREE, "/repo", "s1")
        assert ws == "/ws/worktrees/s1"
        assert isolated is True

    def test_failure_falls_back_to_repo(self):
        svc = _make_service()
        with patch(f"{_MOD}.provision_workspace", side_effect=RuntimeError("no git")):
            ws, isolated = svc._provision(IsolationLevel.WORKTREE, "/repo", "s1")
        assert ws == "/repo"
        assert isolated is False


class TestIsolationDispatch:
    @pytest.mark.asyncio
    async def test_container_gets_real_workspace_mount(self):
        """Fixes empty `-v :/workspace`: spec.workspace must be set."""
        svc = _make_service()
        svc._isolation = IsolationLevel.CONTAINER
        session = TeamSession(team_id="tm1", task_id="p1",
                              subtasks=[_make_task()], repo_dir="/repo")
        captured = {}

        async def _capture(spec):
            captured["workspace"] = spec.workspace
            return "cid1"

        with patch(f"{_MOD}.provision_workspace", return_value="/ws/worktrees/s1"), \
             patch(f"{_MOD}.cleanup_workspace"), \
             patch(f"{_MOD}.async_create_container", new=_capture), \
             patch(f"{_MOD}.async_start_container", new_callable=AsyncMock), \
             patch(f"{_MOD}.async_wait_container", new_callable=AsyncMock, return_value=0), \
             patch(f"{_MOD}.container_logs", return_value=""), \
             patch(f"{_MOD}.async_remove_container", new_callable=AsyncMock):
            result = await svc._run_one(session.subtasks[0], session)
        assert captured["workspace"] == "/ws/worktrees/s1"
        assert result.status == "succeeded"

    @pytest.mark.asyncio
    async def test_worktree_runs_local_not_docker(self):
        """No docker when isolation is worktree — local fallback runs."""
        svc = _make_service()
        svc._isolation = IsolationLevel.WORKTREE
        session = TeamSession(team_id="tm1", task_id="p1",
                              subtasks=[_make_task()], repo_dir="/repo")
        docker = AsyncMock()
        with patch(f"{_MOD}.provision_workspace", return_value="/ws/worktrees/s1"), \
             patch(f"{_MOD}.cleanup_workspace") as clean, \
             patch(f"{_MOD}.async_create_container", new=docker), \
             patch.object(svc, "_run_local", new_callable=AsyncMock, return_value=0) as local:
            result = await svc._run_one(session.subtasks[0], session)
        docker.assert_not_called()
        local.assert_awaited_once()
        clean.assert_called_once()
        assert result.status == "succeeded"

    @pytest.mark.asyncio
    async def test_lock_only_without_repo_runs_local(self):
        svc = _make_service()
        svc._isolation = IsolationLevel.LOCK_ONLY
        session = TeamSession(team_id="tm1", task_id="p1",
                              subtasks=[_make_task()], repo_dir=None)
        with patch.object(svc, "_run_local", new_callable=AsyncMock, return_value=0) as local:
            result = await svc._run_one(session.subtasks[0], session)
        local.assert_awaited_once()
        assert result.status == "succeeded"

    def test_local_command_sandboxed_no_skip_permissions(self):
        svc = _make_service()
        task = Task(title="Add login", source="t", source_ref="r")
        task.description = "JWT based"
        cmd = svc._local_command(task, "firejail --net=none")
        # Sandbox wrapper is prepended; dangerous flag must be absent.
        assert cmd[:2] == ["firejail", "--net=none"]
        assert "claude" in cmd
        assert "--dangerously-skip-permissions" not in cmd
        assert any("Add login" in part for part in cmd)

    @pytest.mark.asyncio
    async def test_run_local_refuses_without_sandbox(self):
        svc = _make_service()
        svc._cfg.orchestrator.local_sandbox = ""
        spec = MagicMock(workspace="/ws")
        with pytest.raises(PermissionError):
            await svc._run_local(spec, _make_task())

    @pytest.mark.asyncio
    async def test_run_local_runs_when_sandboxed(self):
        svc = _make_service()
        svc._cfg.orchestrator.local_sandbox = "firejail"
        spec = MagicMock(workspace="/ws")
        proc = MagicMock(returncode=0)
        with patch(f"{_MOD}.subprocess.run", return_value=proc) as run:
            code = await svc._run_local(spec, _make_task())
        assert code == 0
        assert run.call_args.args[0][0] == "firejail"

    @pytest.mark.asyncio
    async def test_worktree_without_sandbox_fails_safe(self):
        """Worktree isolation + no sandbox => failed, never runs agent."""
        svc = _make_service()
        svc._isolation = IsolationLevel.WORKTREE
        svc._cfg.orchestrator.local_sandbox = ""
        session = TeamSession(team_id="tm1", task_id="p1",
                              subtasks=[_make_task()], repo_dir="/repo")
        with patch(f"{_MOD}.provision_workspace", return_value="/ws/worktrees/s1"), \
             patch(f"{_MOD}.cleanup_workspace"), \
             patch(f"{_MOD}.subprocess.run") as run:
            result = await svc._run_one(session.subtasks[0], session)
        run.assert_not_called()
        assert result.status == "failed"
