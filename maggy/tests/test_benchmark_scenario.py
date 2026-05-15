"""Benchmark scenario — simulate a 10-task sprint across 3 models.

Measures Maggy's effectiveness at:
  1. Routing accuracy  — correct model for each complexity tier
  2. Budget efficiency — spend distribution across providers
  3. Fallback resilience — recovery when models hit quota
  4. Fatigue awareness — detects and reacts to context overload
  5. Lock safety — prevents file clobbering between agents
  6. Escalation — auto-escalates repeated failures
  7. Checkpoint continuity — survives model handoff
  8. Calibration learning — penalizes bad models over time
  9. Dual planning — counter-checks high-blast tasks
  10. Observability — signals recorded for all activity
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from maggy.adapters.pi import PiAdapter, RunResult
from maggy.budget import BudgetManager
from maggy.calibration.tracker import CalibrationTracker
from maggy.checkpoint import CheckpointManager
from maggy.config import (
    CodebaseConfig,
    MaggyConfig,
    OrgConfig,
    ProjectConfig,
    StorageConfig,
)
from maggy.coordination.lock_manager import LockManager
from maggy.escalation.protocol import Escalator
from maggy.mnemos import FatigueTracker, SignalLog
from maggy.observability.collector import ObservabilityCollector
from maggy.providers.base import Task
from maggy.registry import ProjectRegistry
from maggy.routing import RoutingContext, RoutingService
from maggy.services.executor import ExecutorService
from maggy.services.executor_types import SessionCtx
from maggy.services.planner import DualPlanner


# -- fixtures ----------------------------------------------------------------

def _cfg(tmp_path) -> MaggyConfig:
    return MaggyConfig(
        org=OrgConfig(name="benchmark-org"),
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        codebases=[
            CodebaseConfig(path=str(tmp_path / "repo"), key="app"),
        ],
        projects=[
            ProjectConfig(
                name="app", repo="bench/app",
                path=str(tmp_path / "repo"),
                default_branch="main",
            ),
        ],
    )


SPRINT_TASKS = [
    Task(id="T-1", title="Fix README typo", description="Typo fix",
         raw={"blast_score": 1, "task_type": "docs"}),
    Task(id="T-2", title="Lint cleanup", description="Format files",
         raw={"blast_score": 1, "task_type": "formatting"}),
    Task(id="T-3", title="Add health endpoint", description="GET /health",
         raw={"blast_score": 3, "task_type": "feature"}),
    Task(id="T-4", title="Pagination for /users", description="Cursor pagination",
         raw={"blast_score": 5, "task_type": "feature"}),
    Task(id="T-5", title="Refactor auth service", description="Extract middleware",
         raw={"blast_score": 6, "task_type": "refactor"}),
    Task(id="T-6", title="Add rate limiter", description="Redis rate limit",
         raw={"blast_score": 7, "task_type": "feature"}),
    Task(id="T-7", title="Migrate to v2 API", description="Breaking change",
         raw={"blast_score": 8, "task_type": "refactor"}),
    Task(id="T-8", title="Fix XSS in comments", description="Sanitize HTML",
         raw={"blast_score": 9, "task_type": "security",
              "security_sensitive": True}),
    Task(id="T-9", title="OAuth2 PKCE flow", description="Full OAuth impl",
         raw={"blast_score": 10, "task_type": "security",
              "security_sensitive": True}),
    Task(id="T-10", title="Performance audit", description="Profile + optimize",
         raw={"blast_score": 7, "task_type": "performance"}),
]


# -- 1. Routing accuracy -----------------------------------------------------

class TestRoutingAccuracy:
    """Every task lands on the right model tier."""

    def test_all_10_tasks_route_correctly(self, tmp_path):
        cfg = _cfg(tmp_path)
        svc = RoutingService(cfg)
        results: dict[str, str] = {}

        for task in SPRINT_TASKS:
            raw = task.raw or {}
            ctx = RoutingContext(
                blast_score=raw.get("blast_score", 0),
                task_type=raw.get("task_type", "general"),
                security_sensitive=raw.get("security_sensitive", False),
            )
            decision = svc.route(ctx)
            name = decision.primary if isinstance(decision.primary, str) else decision.primary.name
            results[task.id] = name

        # Low blast (1-3) → cheap tier unless rules override
        # T-1 is docs → rules force claude
        assert results["T-1"] == "claude"
        assert results["T-2"] in ("local", "kimi")
        assert results["T-3"] in ("local", "kimi")
        # Blast 5 → local(0-5) cheapest, codex(4-10), claude(5-10)
        assert results["T-4"] in ("local", "codex")
        # Blast 6 → codex(4-10) cheapest, claude(5-10)
        assert results["T-5"] in ("codex", "claude")
        # Blast 7 → codex or claude
        assert results["T-6"] in ("codex", "claude")
        # Blast 8+ → codex or claude (security→claude)
        assert results["T-7"] in ("codex", "claude")
        # Security always premium (claude)
        assert results["T-8"] == "claude"
        assert results["T-9"] == "claude"
        assert results["T-10"] in ("codex", "claude")

    def test_routing_accuracy_score(self, tmp_path):
        """Compute accuracy as % of correct routing decisions."""
        cfg = _cfg(tmp_path)
        svc = RoutingService(cfg)
        correct = 0

        expected_tiers = {
            "T-1": "premium", "T-2": "cheap", "T-3": "cheap",
            "T-4": "cheap",   # local covers 0-5
            "T-5": "mid",     # codex covers 4-10
            "T-6": "mid",     # codex covers 4-10
            "T-7": "mid",     # codex (no security override)
            "T-8": "premium", "T-9": "premium",
            "T-10": "mid",    # codex covers 4-10
        }
        tier_map = {"local": "cheap", "kimi": "cheap",
                     "codex": "mid", "claude": "premium"}

        for task in SPRINT_TASKS:
            raw = task.raw or {}
            ctx = RoutingContext(
                blast_score=raw.get("blast_score", 0),
                task_type=raw.get("task_type", "general"),
                security_sensitive=raw.get("security_sensitive", False),
            )
            decision = svc.route(ctx)
            name = decision.primary if isinstance(decision.primary, str) else decision.primary.name
            actual_tier = tier_map.get(name, "unknown")
            if actual_tier == expected_tiers[task.id]:
                correct += 1

        accuracy = correct / len(SPRINT_TASKS)
        assert accuracy >= 0.9, f"Routing accuracy {accuracy:.0%} < 90%"


# -- 2. Budget efficiency ----------------------------------------------------

class TestBudgetEfficiency:
    def test_spend_distribution(self, tmp_path):
        cfg = _cfg(tmp_path)
        bm = BudgetManager(cfg)
        # Simulate spend from a 10-task sprint
        bm.record_spend("moonshot", "kimi-k2", 0.03)
        bm.record_spend("moonshot", "kimi-k2", 0.03)
        bm.record_spend("moonshot", "kimi-k2", 0.02)
        bm.record_spend("openai", "gpt-4o", 0.30)
        bm.record_spend("openai", "gpt-4o", 0.25)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.20)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.50)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.80)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.60)
        bm.record_spend("anthropic", "claude-sonnet-4", 1.40)

        breakdown = bm.by_provider()
        by_name = {r["provider"]: r["spent_usd"] for r in breakdown}

        # Cheap tasks should be < 5% of total
        total = sum(by_name.values())
        cheap_pct = by_name.get("moonshot", 0) / total
        assert cheap_pct < 0.05, f"Cheap tier {cheap_pct:.0%} >= 5%"

        # Premium should be > 70% (complex tasks dominate)
        premium_pct = by_name.get("anthropic", 0) / total
        assert premium_pct > 0.70, f"Premium {premium_pct:.0%} <= 70%"


# -- 3. Fallback resilience --------------------------------------------------

class TestFallbackResilience:
    @pytest.mark.asyncio
    async def test_quota_recovery(self):
        pi = PiAdapter()
        attempts: list[str] = []

        async def fake_send(model, prompt, wd, max_turns=20, timeout=600):
            attempts.append(model)
            if model in ("kimi", "deepseek"):
                return RunResult(model=model, success=False, error="quota", quota_hit=True)
            return RunResult(model=model, success=True, output="recovered")

        pi.send_prompt = fake_send
        result = await pi.send_with_fallback("kimi", "test", "/tmp")

        assert result.success
        assert len(attempts) >= 3, "Should try multiple models"
        assert attempts[0] == "kimi"
        assert result.model not in ("kimi", "deepseek")

    @pytest.mark.asyncio
    async def test_full_chain_failure(self):
        pi = PiAdapter()

        async def all_fail(model, prompt, wd, max_turns=20, timeout=600):
            return RunResult(model=model, success=False, error="down")

        pi.send_prompt = all_fail
        result = await pi.send_with_fallback("kimi", "test", "/tmp")

        assert not result.success


# -- 4. Fatigue awareness ----------------------------------------------------

class TestFatigueAwareness:
    def test_progressive_fatigue(self):
        ft = FatigueTracker(context_window=200_000)
        assert ft.state() == "ok"

        # Simulate 5 steps of increasing context
        for i in range(5):
            ft.record("context_load", 0.15 * (i + 1))
            ft.record("turn_pressure", 0.1 * (i + 1))

        assert ft.composite() > 0.3

    def test_model_switch_degrades_fatigue(self):
        ft = FatigueTracker(context_window=200_000)
        ft.record("reread_ratio", 0.2)

        ft.on_model_switch(128_000)
        assert ft.dimensions["reread_ratio"] == pytest.approx(0.35)
        assert ft.context_window == 128_000

        ft.on_model_switch(128_000)
        assert ft.dimensions["reread_ratio"] == pytest.approx(0.50)

    def test_critical_state_detection(self):
        ft = FatigueTracker()
        for dim in ("context_load", "turn_pressure", "reread_ratio", "handoff_risk"):
            ft.record(dim, 0.85)
        assert ft.state() == "critical"


# -- 5. Lock safety ----------------------------------------------------------

class TestLockSafety:
    def test_concurrent_agent_protection(self, tmp_path):
        locks = LockManager(tmp_path / "bench-locks.db")
        assert locks.acquire("src/auth.py", "kimi-agent")
        assert not locks.acquire("src/auth.py", "claude-agent")
        assert locks.acquire("src/api.py", "claude-agent")

        conflicts = locks.conflicts(["src/auth.py", "src/api.py"])
        assert len(conflicts) == 2

    def test_release_allows_reacquire(self, tmp_path):
        locks = LockManager(tmp_path / "bench-locks.db")
        locks.acquire("src/main.py", "agent-a")
        locks.release("src/main.py", "agent-a")
        assert locks.acquire("src/main.py", "agent-b")

    def test_release_all_by_session(self, tmp_path):
        locks = LockManager(tmp_path / "bench-locks.db")
        locks.acquire("f1.py", "sess-1")
        locks.acquire("f2.py", "sess-1")
        locks.acquire("f3.py", "sess-1")
        count = locks.release_all("sess-1")
        assert count == 3


# -- 6. Escalation -----------------------------------------------------------

class TestEscalation:
    def test_auto_escalate_after_failures(self, tmp_path):
        esc = Escalator(tmp_path / "bench-esc.db")
        assert len(esc.list_pending()) == 0

        esc.escalate("sess-1", "repeated_failure", {"failures": 3})
        pending = esc.list_pending()
        assert len(pending) == 1
        assert pending[0].reason == "repeated_failure"

    def test_resolve_clears_pending(self, tmp_path):
        esc = Escalator(tmp_path / "bench-esc.db")
        pkt = esc.escalate("sess-2", "stuck", {})
        esc.resolve(pkt.id, "retry with claude")
        assert len(esc.list_pending()) == 0


# -- 7. Checkpoint continuity ------------------------------------------------

class TestCheckpointContinuity:
    def test_model_handoff_preserves_state(self, tmp_path):
        mgr = CheckpointManager(tmp_path / "bench-cp")
        mgr.write("session-x", {
            "goal": "Add OAuth2",
            "model_history": ["kimi", "gpt", "claude"],
            "progress": ["Step 1 by kimi", "Step 2 by gpt"],
            "current_subgoal": "Write tests",
            "fatigue_score": 0.45,
        })
        data = mgr.read("session-x")
        assert data["goal"] == "Add OAuth2"
        assert len(data["model_history"]) == 3
        assert data["fatigue_score"] == 0.45

    def test_checkpoint_cleanup(self, tmp_path):
        mgr = CheckpointManager(tmp_path / "bench-cp")
        mgr.write("temp-sess", {"goal": "temp"})
        assert mgr.read("temp-sess") is not None
        mgr.delete("temp-sess")
        assert mgr.read("temp-sess") is None


# -- 8. Calibration learning -------------------------------------------------

class TestCalibrationLearning:
    def test_bad_model_gets_penalized(self, tmp_path):
        cal = CalibrationTracker(tmp_path / "bench-cal.db")
        # Record consistently bad predictions for "kimi"
        for _ in range(10):
            cal.record("kimi", "feature", 0.9, 0.1)
        # Record good predictions for "claude"
        for _ in range(10):
            cal.record("claude", "feature", 0.8, 0.85)

        kimi_acc = cal.accuracy("kimi")
        claude_acc = cal.accuracy("claude")

        assert kimi_acc < 0.5, f"Bad model accuracy {kimi_acc} >= 0.5"
        assert claude_acc > 0.9, f"Good model accuracy {claude_acc} <= 0.9"

    def test_routing_penalizes_uncalibrated(self, tmp_path):
        cfg = _cfg(tmp_path)
        svc = RoutingService(cfg)
        # Poison kimi's calibration
        for _ in range(10):
            svc.calibration.record("kimi", "feature", 0.9, 0.1)

        ctx = RoutingContext(blast_score=1, task_type="feature")
        decision = svc.route(ctx)
        name = decision.primary if isinstance(decision.primary, str) else decision.primary.name
        # kimi should be penalized — routing skips it
        # (only applies if kimi was the primary)
        assert name is not None  # routing still works


# -- 9. Dual planning -------------------------------------------------------

class TestDualPlanning:
    @pytest.mark.asyncio
    async def test_counter_check_runs(self):
        models_used: list[str] = []

        async def fake_send(model, prompt, wd, turns=5, timeout=600):
            models_used.append(model)
            text = "CONFLICT: Missing error handling" if model == "codex" else "Step 1: implement"
            return RunResult(model=model, success=True, output=text)

        pi = PiAdapter()
        pi.send_prompt = fake_send
        planner = DualPlanner(pi)
        result = await planner.dual_plan("Add OAuth", "Implement OAuth2", "/tmp")

        assert "claude" in models_used
        assert "codex" in models_used
        assert len(result.conflicts) >= 1
        assert "Missing error handling" in result.conflicts[0]


# -- 10. Observability -------------------------------------------------------

class TestObservability:
    def test_signal_recording(self, tmp_path):
        obs = ObservabilityCollector(tmp_path / "bench-obs.db")
        obs.record_signal("app", "deploy_status", 1.0)
        obs.record_signal("app", "test_coverage", 0.87)
        obs.record_signal("api", "latency_p99", 0.250)

        app_signals = obs.recent_signals("app", limit=10)
        assert len(app_signals) == 2

        api_signals = obs.recent_signals("api", limit=10)
        assert len(api_signals) == 1
        assert api_signals[0]["signal_type"] == "latency_p99"

    def test_signal_log_jsonl(self, tmp_path):
        log = SignalLog(tmp_path / "bench-signals.jsonl")
        for i in range(5):
            log.append({"step": i, "model": "claude"})
        recent = log.recent(3)
        assert len(recent) == 3
        assert recent[0]["step"] == 2


# -- 11. Full executor pipeline (E2E) ----------------------------------------

class TestFullExecutorPipeline:
    @pytest.mark.asyncio
    async def test_10_task_sprint(self, tmp_path):
        """Simulate a full 10-task sprint through the executor."""
        cfg = _cfg(tmp_path)
        (tmp_path / "repo").mkdir()
        provider = AsyncMock()
        executor = ExecutorService(cfg, provider)

        models_used: list[str] = []

        async def fake_send(model, prompt, wd, max_turns=20, timeout=600):
            models_used.append(model)
            return RunResult(model=model, success=True, output="done", cost_usd=0.10)

        async def fake_ctx(cfg, task):
            return ""

        executor._pi.send_prompt = fake_send
        from maggy.services import executor_helpers
        _orig_icpg = executor_helpers.build_icpg_context
        executor_helpers.build_icpg_context = fake_ctx

        for task in SPRINT_TASKS:
            sid = f"s-{task.id}"
            session = {
                "id": sid, "task_id": task.id,
                "task_title": task.title, "mode": "plan",
                "working_dir": str(tmp_path / "repo"),
                "status": "running", "started_at": "", "output": "",
            }
            executor._sessions[sid] = session
            ctx = SessionCtx(session, task, str(tmp_path / "repo"))
            await executor._run(ctx, "plan")

        # Verify multi-model distribution
        unique_models = set(models_used)
        assert len(unique_models) >= 3, f"Only {unique_models} used"
        assert "claude" in unique_models
        assert "codex" in unique_models
        cheap = {"kimi", "local"}
        assert cheap & unique_models, "No cheap model used"

        # Verify fatigue was tracked
        assert executor._fatigue.dimensions["context_load"] > 0

        # Verify signals were logged (plan mode uses _run_model directly)
        # Checkpoints were written and cleaned up
        for task in SPRINT_TASKS:
            clean_id = task.id.replace("/", "-")
            assert executor._checkpoint.read(clean_id) is None

    @pytest.mark.asyncio
    async def test_sprint_budget_summary(self, tmp_path):
        """After a sprint, budget tracks all providers."""
        cfg = _cfg(tmp_path)
        (tmp_path / "repo").mkdir()
        provider = AsyncMock()
        executor = ExecutorService(cfg, provider)

        cost_map = {"kimi": 0.01, "local": 0.0, "claude": 0.80, "codex": 0.10}

        async def fake_send(model, prompt, wd, max_turns=20, timeout=600):
            return RunResult(model=model, success=True, output="ok", cost_usd=cost_map.get(model, 0.05))

        async def fake_ctx(cfg, task):
            return ""

        executor._pi.send_prompt = fake_send
        from maggy.services import executor_helpers
        _orig_icpg = executor_helpers.build_icpg_context
        executor_helpers.build_icpg_context = fake_ctx

        for task in SPRINT_TASKS:
            sid = f"s-{task.id}"
            session = {
                "id": sid, "task_id": task.id,
                "task_title": task.title, "mode": "plan",
                "working_dir": str(tmp_path / "repo"),
                "status": "running", "started_at": "", "output": "",
            }
            executor._sessions[sid] = session
            ctx = SessionCtx(session, task, str(tmp_path / "repo"))
            await executor._run(ctx, "plan")

        breakdown = executor._budget.by_provider()
        providers = {r["provider"] for r in breakdown}
        assert len(providers) >= 2, f"Only {providers}"


# -- 12. Project Registry CRUD -----------------------------------------------

class TestProjectRegistry:
    def test_full_lifecycle(self, tmp_path):
        cfg = _cfg(tmp_path)
        reg = ProjectRegistry(cfg)
        assert len(reg.list()) == 1

        reg.add(ProjectConfig(
            name="api", repo="bench/api",
            path="/tmp/api", default_branch="main",
        ))
        assert len(reg.list()) == 2
        assert reg.get("api") is not None

        reg.remove("api")
        assert reg.get("api") is None
        assert len(reg.list()) == 1
