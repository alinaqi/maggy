from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from maggy.adapters.pi import PiAdapter, RunResult
from maggy.budget import BudgetManager
from maggy.checkpoint import CheckpointManager
from maggy.config import MaggyConfig
from maggy.coordination.lock_manager import LockManager
from maggy.escalation.protocol import Escalator
from maggy.mnemos.fatigue import FatigueTracker
from maggy.mnemos.signals import SignalLog
from maggy.providers.base import IssueTrackerProvider
from maggy.recovery.rollback import RollbackManager
from maggy.routing import RoutingService
from maggy.services import executor_helpers as H
from maggy.services import executor_prompts as P
from maggy.services.executor_types import SessionCtx, StepSpec
from maggy.services.planner import DualPlanner

logger = logging.getLogger(__name__)


class ExecutorService:
    def __init__(self, cfg: MaggyConfig, provider: IssueTrackerProvider, status_cb=None):
        self.cfg, self.provider = cfg, provider
        self._pi = PiAdapter()
        self._routing = RoutingService(cfg)
        self._budget = BudgetManager(cfg)
        self._sessions: dict[str, dict] = {}
        self._bg_tasks: set[asyncio.Task] = set()
        db = Path(cfg.storage.path).expanduser().parent
        self._fatigue = FatigueTracker()
        self._signals = SignalLog(db / "signals.jsonl")
        self._locks = LockManager(db / "locks.db")
        self._rollback = RollbackManager()
        self._checkpoint = CheckpointManager(db / "checkpoints")
        self._escalator = Escalator(db / "escalations.db")
        self._planner, self._status_cb = DualPlanner(self._pi), status_cb
    async def start(self, task_id: str, mode: str = "tdd",
                    working_dir: str | None = None) -> str:
        if mode not in ("tdd", "plan"):
            raise ValueError(f"Unknown mode {mode!r}")
        task = await self.provider.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        wd = H.resolve_working_dir(self.cfg, working_dir, task)
        sid = uuid.uuid4().hex[:10]
        self._sessions[sid] = dict(
            id=sid, task_id=task_id, task_title=task.title, mode=mode,
            working_dir=wd, status="running",
            started_at=datetime.now(timezone.utc).isoformat(), output="")
        self._locks.acquire(wd, sid)
        ctx = SessionCtx(self._sessions[sid], task, wd)
        bg = asyncio.create_task(self._run(ctx, mode))
        self._bg_tasks.add(bg)
        bg.add_done_callback(self._bg_tasks.discard)
        return sid

    def get_session(self, sid: str) -> dict | None: return self._sessions.get(sid)
    def list_sessions(self) -> list[dict]: return list(self._sessions.values())
    async def _run(self, ctx: SessionCtx, mode: str) -> None:
        try:
            from maggy.services.convention_inferrer import ensure_inferred
            from maggy.services.convention_scanner import ensure_scanned
            pk = str(ctx.task.raw.get("project_key", ""))
            ensure_scanned(self._routing.rules, pk, ctx.wd)
            await ensure_inferred(self._routing.rules, pk, ctx.wd, self._pi)
            ctx.icpg = await H.build_icpg_context(self.cfg, ctx.task)
            await (self._run_plan(ctx) if mode == "plan" else self._run_tdd(ctx))
        except Exception as e:
            logger.exception("Execution failed")
            ctx.session["status"], ctx.session["error"] = "failed", str(e)
        finally:
            self._locks.release_all(ctx.session["id"])
            self._checkpoint.delete(ctx.task.id.replace("/", "-"))

    async def _run_plan(self, ctx: SessionCtx) -> None:
        result = await self._run_model(ctx, P.plan_prompt(ctx.task, ctx.icpg, self._routing), 5)
        ctx.session["output"] = result.output[:10000]
        ctx.session["status"] = "completed" if result.success else "failed"
        if not result.success:
            ctx.session["error"] = result.output[:500]
        elif result.output:
            await H.post_plan(self.provider, ctx.task.id, result.output)

    async def _run_tdd(self, ctx: SessionCtx) -> None:
        if H.blast_score(ctx.task) >= 7:
            await self._dual_plan(ctx)
        prompt = P.analysis_prompt(ctx.task, ctx.icpg, self._routing)
        ok, analysis = await self._reviewed_step(ctx, StepSpec("ANALYZE", prompt, 5))
        if not ok:
            return
        prompt = P.tests_prompt(ctx.task, ctx.icpg, analysis, self._routing)
        ok, _ = await self._reviewed_step(ctx, StepSpec("WRITE TESTS", prompt, 15))
        if not ok:
            return
        if not await self._verify_red(ctx):
            return
        await H.save_rollback(self._rollback, ctx.session["id"], ctx.wd)
        prompt = P.impl_prompt(ctx.task, ctx.icpg, self._routing)
        ok, _ = await self._reviewed_step(ctx, StepSpec("IMPLEMENT", prompt, 25))
        if not ok:
            await H.try_rollback(self._rollback, ctx.session["id"], ctx.wd)
            H.maybe_escalate(self._escalator, ctx.session, ctx.task)
            return
        if not await self._verify_green(ctx):
            await H.try_rollback(self._rollback, ctx.session["id"], ctx.wd)
            return
        ctx.session["status"] = "completed"
        ctx.session["completed_at"] = datetime.now(timezone.utc).isoformat()

    async def _reviewed_step(self, ctx: SessionCtx, step: StepSpec) -> tuple[bool, str]:
        for attempt in range(2):
            ok, output = await self._run_step(ctx, step)
            if not ok:
                return ok, output
            if await self._review_step(ctx, step, output):
                return True, output
            if attempt == 0:
                ctx.session["output"] += f"\n--- RETRY {step.label} ---\n"
        ctx.session.update(status="failed", error=f"Review gate failed for {step.label}")
        return False, output

    async def _run_step(self, ctx: SessionCtx, step: StepSpec) -> tuple[bool, str]:
        result = await self._run_model(ctx, step.prompt, step.max_turns)
        ctx.session["output"] += f"\n=== {step.label} ===\n{result.output[:2000]}\n"
        H.log_signal(self._signals, ctx.session["id"], step.label, result)
        if not result.success:
            ctx.session["status"] = "failed"
        return result.success, result.output

    async def _review_step(self, ctx: SessionCtx, step: StepSpec, output: str) -> bool:
        from maggy.services.output_reviewer import review_output
        review = await review_output(self._pi, step.label, output, ctx.wd)
        ctx.session["output"] += f"\n--- REVIEW {step.label}: {review.score}/5 ---\n"
        return review.score >= 3

    async def _run_model(self, ctx: SessionCtx, prompt: str, turns: int) -> RunResult:
        decision = H.route_model(ctx.task, self._routing)
        name = H.model_name(decision.primary)
        H.write_checkpoint(self._checkpoint, ctx.task, name)
        self._emit_status(name, "running")
        result = await self._send(decision, name, prompt, ctx)
        self._emit_status(name, "done")
        if result.model != name and (e := self._pi.get_model(result.model)):
            self._fatigue.on_model_switch(e.context_window)
        H.track_fatigue(self._fatigue, result)
        if result.cost_usd > 0 or result.input_tokens > 0:
            self._budget.record_spend(
                decision.primary.provider, result.model, result.cost_usd,
                result.input_tokens, result.output_tokens)
        return result

    async def _send(self, decision, name, prompt, ctx):
        cascade = self._routing.rules.cascade
        if not cascade.enabled or H.blast_score(ctx.task) < cascade.min_blast:
            return await self._pi.send_with_fallback(name, prompt, ctx.wd)
        from maggy.services.cascade import cascade_execute
        from maggy.services.output_reviewer import review_output
        chain = [name] + decision.fallback_chain

        async def gate(output: str) -> int:
            return (await review_output(self._pi, "CASCADE", output, ctx.wd)).score
        cr = await cascade_execute(self._pi, chain, prompt, ctx.wd, gate)
        return RunResult(model=cr.model, success=bool(cr.output), output=cr.output, cost_usd=cr.cost_usd)

    def _emit_status(self, agent: str, status: str) -> None:
        if self._status_cb:
            self._status_cb({"type": "agent_status", "agent": agent, "status": status})
    async def _verify_red(self, ctx: SessionCtx) -> bool:
        from maggy.services.tdd_verifier import verify_tests_exist, verify_tests_fail
        for check, prefix in [(verify_tests_exist, "RED: no tests"), (verify_tests_fail, "RED")]:
            r = await check(ctx.wd)
            if not r.passed:
                ctx.session["status"], ctx.session["error"] = "failed", f"{prefix}: {r.detail}"
                return False
        ctx.session["output"] += f"\n=== RED ===\n{r.detail}\n"
        return True
    async def _verify_green(self, ctx: SessionCtx) -> bool:
        from maggy.services.tdd_verifier import verify_coverage, verify_lint, verify_tests_pass
        if not (green := await verify_tests_pass(ctx.wd)).passed:
            ctx.session["status"], ctx.session["error"] = "failed", f"GREEN: {green.detail}"
            return False
        for label, check in [("LINT", verify_lint), ("COVERAGE", verify_coverage)]:
            if not (r := await check(ctx.wd)).passed:
                ctx.session["output"] += f"\n=== {label} ===\n{r.detail}\n"
        ctx.session["output"] += "\n=== VALIDATE ===\nPassed\n"
        return True

    async def _dual_plan(self, ctx: SessionCtx) -> None:
        try:
            r = await self._planner.dual_plan(ctx.task.title, ctx.task.description[:1500], ctx.wd)
            ctx.session.update(dual_plan=r.primary_plan[:2000], plan_conflicts=r.conflicts or [])
        except Exception as exc:
            logger.warning("DualPlanner failed: %s", exc)
