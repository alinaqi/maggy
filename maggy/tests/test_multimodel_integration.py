"""Integration test — small project with tasks across kimi, gpt, claude.

Simulates Maggy routing a batch of tasks with varying complexity through
the full executor pipeline, verifying each lands on the correct model
and that budget/fallback/checkpoint systems work end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from maggy.adapters.pi import PiAdapter, RunResult
from maggy.budget import BudgetManager, TaskSpendTracker
from maggy.checkpoint import CheckpointManager
from maggy.config import (
    CodebaseConfig,
    MaggyConfig,
    OrgConfig,
    ProjectConfig,
    StorageConfig,
)
from maggy.coordination.lock_manager import LockManager
from maggy.mnemos.fatigue import FatigueTracker
from maggy.providers.base import Task
from maggy.routing import RoutingContext, RoutingService
from maggy.services.executor import ExecutorService
from maggy.services.executor_types import SessionCtx
from maggy.services.planner import DualPlanner


# -- helpers ---------------------------------------------------------------

def _project_cfg(tmp_path) -> MaggyConfig:
    return MaggyConfig(
        org=OrgConfig(name="acme"),
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        codebases=[
            CodebaseConfig(path=str(tmp_path / "repo"), key="webapp"),
        ],
        projects=[
            ProjectConfig(
                name="webapp",
                repo="acme/webapp",
                path=str(tmp_path / "repo"),
                default_branch="main",
            ),
        ],
    )


def _task(blast: int, ttype: str, title: str) -> Task:
    return Task(
        id=f"TASK-{blast}",
        title=title,
        description=f"A {ttype} task with blast={blast}.",
        raw={
            "blast_score": blast,
            "task_type": ttype,
            "security_sensitive": ttype == "security",
        },
    )


TASKS = [
    _task(1, "docs", "Update README typo"),
    _task(2, "formatting", "Fix lint warnings"),
    _task(5, "feature", "Add pagination to API"),
    _task(7, "refactor", "Extract auth middleware"),
    _task(9, "security", "Patch XSS in comments"),
]


# -- 1. Routing decisions --------------------------------------------------

class TestRoutingDecisions:
    """Verify correct model selection per complexity."""

    def test_low_blast_routes_to_cheap_tier(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        svc = RoutingService(cfg)
        for blast in (1, 2):
            # Use "formatting" — "docs" is now rules-overridden
            ctx = RoutingContext(blast_score=blast, task_type="formatting")
            decision = svc.route(ctx)
            assert decision.primary.cost_rank <= 2, (
                f"blast={blast} should route to cheap tier"
            )
            assert decision.primary.name in ("local", "kimi")

    def test_mid_blast_routes_to_cheapest_capable(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        svc = RoutingService(cfg)
        ctx = RoutingContext(blast_score=5, task_type="feature")
        decision = svc.route(ctx)
        assert decision.primary.name in ("local", "codex")

    def test_blast_6_routes_to_codex(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        svc = RoutingService(cfg)
        ctx = RoutingContext(blast_score=6, task_type="feature")
        decision = svc.route(ctx)
        assert decision.primary.name == "codex"

    def test_high_blast_routes_to_codex_or_claude(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        svc = RoutingService(cfg)
        ctx = RoutingContext(blast_score=9, task_type="refactor")
        decision = svc.route(ctx)
        assert decision.primary.name in ("codex", "claude")

    def test_security_routes_to_claude(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        svc = RoutingService(cfg)
        ctx = RoutingContext(
            blast_score=3, task_type="security",
            security_sensitive=True,
        )
        decision = svc.route(ctx)
        # Security rule override → claude
        name = decision.primary if isinstance(
            decision.primary, str,
        ) else decision.primary.name
        assert name == "claude"


# -- 2. Full executor pipeline with mocked models -------------------------

class TestExecutorPipeline:
    """End-to-end executor routing with fake model responses."""

    @pytest.mark.asyncio
    async def test_distributes_across_models(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        (tmp_path / "repo").mkdir()
        provider = AsyncMock()
        executor = ExecutorService(cfg, provider)

        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            return RunResult(
                model=model_name, success=True,
                output="done", cost_usd=0.10,
            )

        async def fake_ctx(cfg, task):
            return ""

        executor._pi.send_prompt = fake_send
        from maggy.services import executor_helpers
        executor_helpers.build_icpg_context = fake_ctx

        for task in TASKS:
            sid = f"s-{task.id}"
            session = {
                "id": sid, "task_id": task.id,
                "task_title": task.title, "mode": "plan",
                "working_dir": str(tmp_path / "repo"),
                "status": "running", "started_at": "",
                "output": "",
            }
            executor._sessions[sid] = session
            ctx = SessionCtx(session, task, str(tmp_path / "repo"))
            await executor._run(ctx, "plan")

        # Verify each complexity tier used a different model
        cheap = {"local", "kimi"}
        assert cheap & set(calls), "Low-blast should use cheap tier"
        assert "codex" in calls, "Mid-blast should use codex"
        assert "claude" in calls, "Security should use claude"
        assert len(set(calls)) >= 3, (
            f"Expected >= 3 distinct models, got {set(calls)}"
        )


# -- 3. Budget tracking across providers ----------------------------------

class TestCrossProviderBudget:
    def test_spend_tracked_per_provider(self, tmp_path):
        cfg = _project_cfg(tmp_path)
        bm = BudgetManager(cfg)
        bm.record_spend("moonshot", "kimi-k2", 0.05)
        bm.record_spend("openai", "gpt-4o", 0.30)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.20)

        breakdown = bm.by_provider()
        providers = {r["provider"] for r in breakdown}
        assert providers == {"moonshot", "openai", "anthropic"}

    def test_task_spend_halts_at_limit(self):
        tracker = TaskSpendTracker(max_spend=1.0)
        tracker.record(0.3)
        tracker.record(0.3)
        tracker.record(0.5)
        assert tracker.is_exceeded()
        assert tracker.total() == pytest.approx(1.1)


# -- 4. Fallback chain on quota -------------------------------------------

class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self):
        pi = PiAdapter()
        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            if model_name in ("kimi", "deepseek"):
                return RunResult(
                    model=model_name, success=False,
                    error="quota", quota_hit=True,
                )
            return RunResult(
                model=model_name, success=True, output="ok",
            )

        pi.send_prompt = fake_send
        result = await pi.send_with_fallback(
            "kimi", "test prompt", "/tmp",
        )
        assert result.success
        assert result.model != "kimi"
        assert len(calls) > 1


# -- 5. Checkpoint survives model switch -----------------------------------

class TestCheckpointHandoff:
    def test_checkpoint_roundtrip(self, tmp_path):
        mgr = CheckpointManager(tmp_path / "checkpoints")
        mgr.write("session-abc", {
            "goal": "Ship auth feature",
            "constraints": ["Keep tests green"],
            "progress": ["Step 1 done by kimi"],
            "model_history": ["kimi", "claude"],
            "current_subgoal": "Write integration tests",
            "fatigue_score": 0.35,
        })
        data = mgr.read("session-abc")
        assert data is not None
        assert data["goal"] == "Ship auth feature"
        assert data["model_history"] == ["kimi", "claude"]
        assert data["fatigue_score"] == 0.35


# -- 6. Dual planning uses different models --------------------------------

class TestDualPlanning:
    @pytest.mark.asyncio
    async def test_plan_and_review_use_separate_models(self):
        models_used: list[str] = []
        pi = MagicMock()

        async def fake_send(model, prompt, wd, turns=5):
            models_used.append(model)
            return RunResult(
                model=model, success=True, output="plan output",
            )

        pi.send_prompt = fake_send
        planner = DualPlanner(pi)
        result = await planner.dual_plan(
            "Add OAuth", "Implement OAuth2 flow", "/tmp",
        )
        assert "claude" in models_used
        assert "codex" in models_used
        assert result.primary_plan == "plan output"


# -- 7. Fatigue tracks model switches --------------------------------------

class TestFatigueAcrossModels:
    def test_model_switch_increases_fatigue(self):
        tracker = FatigueTracker(context_window=200_000)
        tracker.record("context_load", 0.3)
        tracker.record("reread_ratio", 0.2)
        assert tracker.state() == "ok"

        tracker.on_model_switch(128_000)
        assert tracker.context_window == 128_000
        assert tracker.dimensions["reread_ratio"] == 0.35

        tracker.on_model_switch(128_000)
        assert tracker.dimensions["reread_ratio"] == 0.50


# -- 8. Lock coordination between agents -----------------------------------

class TestLockCoordination:
    def test_agents_cant_clobber_each_other(self, tmp_path):
        locks = LockManager(tmp_path / "locks.db")
        assert locks.acquire("src/auth.py", "kimi-agent")
        assert not locks.acquire("src/auth.py", "claude-agent")
        assert locks.acquire("src/api.py", "claude-agent")
        conflicts = locks.conflicts(["src/auth.py", "src/api.py"])
        assert "src/auth.py" in conflicts
        assert "src/api.py" in conflicts
        locks.release("src/auth.py", "kimi-agent")
        assert locks.acquire("src/auth.py", "claude-agent")
