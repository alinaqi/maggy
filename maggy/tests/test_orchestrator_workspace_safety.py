"""Orchestrator must never discard unmerged isolated subtask work."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.orchestrator.isolation import IsolationLevel
from maggy.orchestrator.models import Task as OrchTask
from maggy.services.orchestrator import OrchestratorService, TeamSession

_ORC = "maggy.services.orchestrator"
_MRG = "maggy.orchestrator.merge"


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
         patch(f"{_ORC}.safe_merge", return_value=merged) as merge, \
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


@pytest.mark.asyncio
async def test_orchestrator_merge_oserror_keeps_workspace():
    svc = _orch()
    session = TeamSession(team_id="tm1", task_id="p1", repo_dir="/repo",
                          subtasks=[OrchTask(title="x", source="t", source_ref="r")])
    with patch(f"{_ORC}.provision_workspace", return_value="/ws/sub"), \
         patch(f"{_MRG}._generate_patch", return_value=b"diff"), \
         patch(f"{_MRG}._apply_patch", side_effect=OSError("disk full")), \
         patch(f"{_ORC}.cleanup_workspace") as clean, \
         patch.object(svc, "_run_local", new_callable=AsyncMock, return_value=0):
        result = await svc._run_one(session.subtasks[0], session)
    clean.assert_not_called()
    assert result.status == "failed"
    assert result.artifacts["workspace"] == "/ws/sub"
