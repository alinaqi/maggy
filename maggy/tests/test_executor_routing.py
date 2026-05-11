"""Tests for executor model routing and spend recording."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from maggy.adapters.pi import RunResult
from maggy.providers.base import Task
from maggy.services.executor import ExecutorService


def _session() -> dict[str, str]:
    return {
        "id": "session-1",
        "task_id": "task-1",
        "task_title": "Test task",
        "mode": "plan",
        "working_dir": ".",
        "status": "running",
        "started_at": "",
        "output": "",
    }


def _task(blast_score: int, task_type: str) -> Task:
    return Task(
        id="task-1",
        title="Route this task",
        description="Use task metadata for routing.",
        raw={
            "blast_score": blast_score,
            "task_type": task_type,
            "security_sensitive": task_type == "security",
        },
    )


def _patch_executor(executor, monkeypatch):
    """Wire fake send_prompt and context builder."""
    calls: list[str] = []

    async def fake_context(task: Task, wd: str) -> str:
        return ""

    async def fake_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        calls.append(model_name)
        return RunResult(model=model_name, success=True, output="ok")

    monkeypatch.setattr(executor, "_build_icpg_context", fake_context)
    monkeypatch.setattr(executor._pi, "send_prompt", fake_send)
    return calls


@pytest.mark.asyncio
async def test_plan_mode_routes_high_blast_to_claude(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    executor._sessions["session-1"] = _session()
    calls = _patch_executor(executor, monkeypatch)

    await executor._run("session-1", _task(9, "general"), str(tmp_path), "plan")

    assert calls == ["claude"]


@pytest.mark.asyncio
async def test_plan_mode_records_spend_for_selected_model(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    executor._sessions["session-1"] = _session()

    async def fake_context(task: Task, wd: str) -> str:
        return ""

    async def fake_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        return RunResult(
            model=model_name, success=True, output="plan", cost_usd=1.25,
        )

    monkeypatch.setattr(executor, "_build_icpg_context", fake_context)
    monkeypatch.setattr(executor._pi, "send_prompt", fake_send)

    await executor._run("session-1", _task(3, "security"), str(tmp_path), "plan")

    assert executor._budget.today_spend("openai") == pytest.approx(1.25)


@pytest.mark.asyncio
async def test_tdd_high_blast_calls_dual_planner(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    executor._sessions["session-1"] = _session()
    _patch_executor(executor, monkeypatch)

    planner_called = []

    async def track_dual_plan(session, task, wd):
        planner_called.append(True)
        # Skip actual dual planning
        return

    monkeypatch.setattr(executor, "_dual_plan", track_dual_plan)

    await executor._run("session-1", _task(9, "feature"), str(tmp_path), "tdd")
    assert planner_called, "DualPlanner should be called for blast >= 7"


@pytest.mark.asyncio
async def test_locks_released_after_run(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    executor._sessions["session-1"] = _session()
    _patch_executor(executor, monkeypatch)

    wd = str(tmp_path)
    executor._locks.acquire(wd, "session-1")
    await executor._run("session-1", _task(3, "docs"), wd, "plan")

    # Lock should be released after _run completes
    assert executor._locks.acquire(wd, "other-agent")


@pytest.mark.asyncio
async def test_fatigue_tracked_during_steps(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    executor._sessions["session-1"] = _session()
    _patch_executor(executor, monkeypatch)

    await executor._run("session-1", _task(3, "docs"), str(tmp_path), "plan")

    assert executor._fatigue.dimensions["context_load"] > 0
