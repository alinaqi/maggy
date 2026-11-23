"""Executor/orchestrator must never discard unmerged isolated work."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.orchestrator.isolation import IsolationLevel
from maggy.orchestrator.models import Task as OrchTask
from maggy.providers.base import Task
from maggy.services import executor_helpers
from maggy.services.executor import ExecutorService
from maggy.services.executor_types import SessionCtx
from maggy.services.orchestrator import OrchestratorService, TeamSession

_ISO = "maggy.orchestrator.isolation"
_MRG = "maggy.orchestrator.merge"
_ORC = "maggy.services.orchestrator"


def _ctx(parallel: bool = False) -> SessionCtx:
    session = {"id": "s1", "working_dir": "/ws/s1", "repo_dir": "/repo",
               "status": "running", "output": ""}
    task = Task(id="t1", title="T", description="d", raw={"parallel": parallel})
    return SessionCtx(session=session, task=task, wd="/ws/s1")


def _executor(mock_cfg, monkeypatch) -> ExecutorService:
    ex = ExecutorService(mock_cfg, AsyncMock())
    ex._orchestrator = MagicMock(spawn_team=AsyncMock(), decompose=AsyncMock())

    async def no_icpg(cfg, task):
        return ""
    monkeypatch.setattr(executor_helpers, "build_icpg_context", no_icpg)
    monkeypatch.setattr(f"{_ISO}.cleanup_workspace", MagicMock())
    return ex


@pytest.mark.asyncio
async def test_parallel_request_runs_sequential_tdd(mock_cfg, monkeypatch):
    ex = _executor(mock_cfg, monkeypatch)
    ctx = _ctx(parallel=True)
    tdd = AsyncMock()
    monkeypatch.setattr(ex, "_run_tdd", tdd)
    await ex._run(ctx, "tdd")
    tdd.assert_awaited_once()
    ex._orchestrator.spawn_team.assert_not_called()
    assert ctx.session["status"] != "parallel_running"


async def _finish(ex, ctx, merged):
    async def done(c):
        c.session["status"] = "completed"
    with patch.object(ex, "_run_tdd", new=done), \
         patch(f"{_MRG}.merge_changes", return_value=merged) as merge, \
         patch(f"{_ISO}.cleanup_workspace") as clean:
        await ex._run(ctx, "tdd")
    return merge, clean


@pytest.mark.asyncio
async def test_failed_merge_preserves_workspace(mock_cfg, monkeypatch):
    ex = _executor(mock_cfg, monkeypatch)
    ctx = _ctx()
    merge, clean = await _finish(ex, ctx, merged=False)
    merge.assert_called_once()
    clean.assert_not_called()
    assert ctx.session["preserved_workspace"] == "/ws/s1"
    assert ctx.session["status"] == "merge_failed"


@pytest.mark.asyncio
async def test_successful_merge_cleans_workspace(mock_cfg, monkeypatch):
    ex = _executor(mock_cfg, monkeypatch)
    ctx = _ctx()
    _, clean = await _finish(ex, ctx, merged=True)
    clean.assert_called_once()
    assert "preserved_workspace" not in ctx.session
    assert ctx.session["status"] == "completed"


@pytest.mark.asyncio
async def test_failed_run_preserves_workspace(mock_cfg, monkeypatch):
    ex = _executor(mock_cfg, monkeypatch)
    ctx = _ctx()
    with patch.object(ex, "_run_tdd", new=AsyncMock(side_effect=RuntimeError("x"))), \
         patch(f"{_MRG}.merge_changes") as merge, \
         patch(f"{_ISO}.cleanup_workspace") as clean:
        await ex._run(ctx, "tdd")
    merge.assert_not_called()
    clean.assert_not_called()
    assert ctx.session["preserved_workspace"] == "/ws/s1"


def _orch() -> OrchestratorService:
    cfg = MagicMock()
    cfg.orchestrator.workspace_root = "/tmp/maggy-ws"
    svc = OrchestratorService(cfg=cfg)
    svc._isolation = IsolationLevel.WORKTREE
    return svc


async def _run_one(code: int, merged: bool):
    svc = _orch()
    session = TeamSession(team_id="tm1", task_id="p1", repo_dir="/repo",
                          subtasks=[OrchTask(title="x", source="t", source_ref="r")])
    with patch(f"{_ORC}.provision_workspace", return_value="/ws/sub"), \
         patch(f"{_ORC}.merge_changes", return_value=merged) as merge, \
         patch(f"{_ORC}.cleanup_workspace") as clean, \
         patch.object(svc, "_run_local", new_callable=AsyncMock, return_value=code):
        result = await svc._run_one(session.subtasks[0], session)
    return result, merge, clean


@pytest.mark.asyncio
async def test_orchestrator_keeps_failed_subtask_workspace():
    result, merge, clean = await _run_one(code=1, merged=True)
    merge.assert_not_called()
    clean.assert_not_called()
    assert result.artifacts["workspace"] == "/ws/sub"


@pytest.mark.asyncio
async def test_orchestrator_keeps_unmerged_subtask_workspace():
    result, merge, clean = await _run_one(code=0, merged=False)
    merge.assert_called_once()
    clean.assert_not_called()
    assert result.artifacts["workspace"] == "/ws/sub"
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_orchestrator_merges_then_cleans_subtask_workspace():
    result, merge, clean = await _run_one(code=0, merged=True)
    merge.assert_called_once()
    clean.assert_called_once()
    assert "workspace" not in result.artifacts
    assert result.status == "succeeded"
