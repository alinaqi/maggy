"""Tests for executor model routing and spend recording."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from maggy.adapters.pi import RunResult
from maggy.providers.base import Task
from maggy.services import executor_helpers
from maggy.services import output_reviewer as reviewer_mod
from maggy.services.executor import ExecutorService
from maggy.services.executor_types import SessionCtx


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


def _ctx(session: dict, task: Task, wd: str) -> SessionCtx:
    return SessionCtx(session=session, task=task, wd=wd)


def _patch_executor(executor, monkeypatch):
    """Wire fake send_prompt and context builder."""

    async def fake_context(cfg, task):
        return ""

    async def fake_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        return RunResult(
            model=model_name, success=True, output="ok",
        )

    monkeypatch.setattr(
        executor_helpers, "build_icpg_context", fake_context,
    )
    monkeypatch.setattr(executor._pi, "send_prompt", fake_send)


@pytest.mark.asyncio
async def test_plan_mode_routes_high_blast_to_claude(
    mock_cfg, tmp_path, monkeypatch,
):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    models: list[str] = []

    async def fake_context(cfg, task):
        return ""

    async def tracking_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        models.append(model_name)
        return RunResult(model=model_name, success=True, output="ok")

    monkeypatch.setattr(executor_helpers, "build_icpg_context", fake_context)
    monkeypatch.setattr(executor._pi, "send_prompt", tracking_send)
    task = _task(9, "general")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    # Blast 9 general → codex (cost_rank=3, covers 4-10)
    assert models[0] == "codex"


@pytest.mark.asyncio
async def test_plan_records_spend(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session

    async def fake_context(cfg, task):
        return ""

    async def fake_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        return RunResult(
            model=model_name, success=True,
            output="plan", cost_usd=1.25,
        )

    monkeypatch.setattr(executor_helpers, "build_icpg_context", fake_context)
    monkeypatch.setattr(executor._pi, "send_prompt", fake_send)
    task = _task(3, "security")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    assert executor._budget.today_spend("anthropic") == pytest.approx(1.25)


@pytest.mark.asyncio
async def test_tdd_high_blast_calls_dual_planner(
    mock_cfg, tmp_path, monkeypatch,
):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    planner_called = []

    async def track_dual(ctx):
        planner_called.append(True)

    monkeypatch.setattr(executor, "_dual_plan", track_dual)
    task = _task(9, "feature")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "tdd")
    assert planner_called


@pytest.mark.asyncio
async def test_locks_released_after_run(
    mock_cfg, tmp_path, monkeypatch,
):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    wd = str(tmp_path)
    executor._locks.acquire(wd, "session-1")
    task = _task(3, "docs")
    ctx = _ctx(session, task, wd)
    await executor._run(ctx, "plan")
    assert executor._locks.acquire(wd, "other-agent")


@pytest.mark.asyncio
async def test_fatigue_tracked(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    task = _task(3, "docs")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    assert executor._fatigue.dimensions["context_load"] > 0


@pytest.mark.asyncio
async def test_conventions_in_prompts(
    mock_cfg, tmp_path, monkeypatch,
):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    prompts: list[str] = []

    async def fake_context(cfg, task):
        return ""

    async def fake_send(
        model_name: str, prompt: str, working_dir: str,
        max_turns: int = 20, timeout: int = 600,
    ) -> RunResult:
        prompts.append(prompt)
        return RunResult(model=model_name, success=True, output="ok")

    monkeypatch.setattr(executor_helpers, "build_icpg_context", fake_context)
    monkeypatch.setattr(executor._pi, "send_prompt", fake_send)
    task = _task(5, "feature")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    assert prompts
    assert "Team Conventions" in prompts[0]
    assert "minimum wowable product" in prompts[0]


@pytest.mark.asyncio
async def test_tdd_calls_reviewer(mock_cfg, tmp_path, monkeypatch):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    reviews: list[str] = []

    async def fake_review(pi, label, output, wd):
        reviews.append(label)
        from maggy.services.output_reviewer import ReviewResult
        return ReviewResult(score=4, reason="ok")

    monkeypatch.setattr(reviewer_mod, "review_output", fake_review)
    task = _task(3, "feature")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "tdd")
    assert "ANALYZE" in reviews
    assert "WRITE TESTS" in reviews


@pytest.mark.asyncio
async def test_review_retry_on_low_score(
    mock_cfg, tmp_path, monkeypatch,
):
    provider = AsyncMock()
    executor = ExecutorService(mock_cfg, provider)
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    call_count = [0]

    async def fake_review(pi, label, output, wd):
        call_count[0] += 1
        from maggy.services.output_reviewer import ReviewResult
        if call_count[0] == 1:
            return ReviewResult(score=2, reason="poor")
        return ReviewResult(score=4, reason="ok")

    monkeypatch.setattr(reviewer_mod, "review_output", fake_review)
    task = _task(3, "feature")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "tdd")
    assert call_count[0] >= 2
    assert "RETRY" in session["output"]


@pytest.mark.asyncio
async def test_status_callback_fires(
    mock_cfg, tmp_path, monkeypatch,
):
    """Status callback receives running/done events."""
    provider = AsyncMock()
    statuses: list[dict] = []
    executor = ExecutorService(
        mock_cfg, provider, status_cb=statuses.append,
    )
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    task = _task(3, "docs")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    assert any(s["status"] == "running" for s in statuses)
    assert any(s["status"] == "done" for s in statuses)


@pytest.mark.asyncio
async def test_status_shows_model_name(
    mock_cfg, tmp_path, monkeypatch,
):
    """Status events include the routed model name."""
    provider = AsyncMock()
    statuses: list[dict] = []
    executor = ExecutorService(
        mock_cfg, provider, status_cb=statuses.append,
    )
    session = _session()
    executor._sessions["session-1"] = session
    _patch_executor(executor, monkeypatch)
    task = _task(9, "general")
    ctx = _ctx(session, task, str(tmp_path))
    await executor._run(ctx, "plan")
    agents = {s.get("agent") for s in statuses}
    assert "codex" in agents
