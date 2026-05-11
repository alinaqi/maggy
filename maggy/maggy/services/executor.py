"""Executor — TDD pipeline that spawns claude -p with iCPG-enriched prompts.

Reuses Maggy's iCPG CLI for codebase intelligence. Picks the right
working directory based on ticket keywords and configured codebase paths.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
from maggy.process.model_router import RoutingDecision
from maggy.providers.base import IssueTrackerProvider, Task
from maggy.recovery.rollback import RollbackManager
from maggy.routing import RoutingContext, RoutingService
from maggy.services.planner import DualPlanner

logger = logging.getLogger(__name__)

CLAUDE_BIN = "claude"


class ExecutorService:
    def __init__(self, cfg: MaggyConfig, provider: IssueTrackerProvider):
        self.cfg = cfg
        self.provider = provider
        self._pi = PiAdapter()
        self._routing = RoutingService(cfg)
        self._budget = BudgetManager(cfg)
        self._sessions: dict[str, dict] = {}
        self._bg_tasks: set[asyncio.Task] = set()
        db_dir = Path(cfg.storage.path).expanduser().parent
        self._fatigue = FatigueTracker()
        self._signals = SignalLog(db_dir / "signals.jsonl")
        self._locks = LockManager(db_dir / "locks.db")
        self._rollback = RollbackManager()
        self._checkpoint = CheckpointManager(db_dir / "checkpoints")
        self._escalator = Escalator(db_dir / "escalations.db")
        self._planner = DualPlanner(self._pi)

    async def start(self, task_id: str, mode: str = "tdd", working_dir: str | None = None) -> str:
        """Spawn a Claude Code session for this task. Returns session_id.

        mode='tdd' runs the full plan→tests→implement cycle.
        mode='plan' generates a plan only and posts to the ticket.
        """
        if mode not in ("tdd", "plan"):
            raise ValueError(f"Unknown mode {mode!r} — expected 'tdd' or 'plan'")

        task = await self.provider.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Resolve & validate working_dir against configured codebase roots.
        # Prevents a caller from running claude --dangerously-skip-permissions
        # in arbitrary filesystem locations.
        wd = self._resolve_working_dir(working_dir, task)
        session_id = uuid.uuid4().hex[:10]

        session = {
            "id": session_id,
            "task_id": task_id,
            "task_title": task.title,
            "mode": mode,
            "working_dir": wd,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "output": "",
        }
        self._sessions[session_id] = session
        self._locks.acquire(wd, session_id)

        bg = asyncio.create_task(self._run(session_id, task, wd, mode))
        self._bg_tasks.add(bg)
        bg.add_done_callback(self._bg_tasks.discard)
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        return list(self._sessions.values())

    def _resolve_working_dir(self, requested: str | None, task: Task) -> str:
        """Resolve working_dir, enforcing it stays inside a configured codebase.

        If `requested` is None → auto-pick via keyword match.
        If `requested` is provided → resolve to absolute path and verify it's
        inside one of the configured codebase roots (prevents arbitrary cwd).
        Raises ValueError on violation.
        """
        if not self.cfg.codebases:
            raise ValueError("No codebases configured")

        # Build the allowed roots set (absolute, resolved)
        allowed_roots = [Path(c.path).expanduser().resolve() for c in self.cfg.codebases]

        if requested:
            candidate = Path(requested).expanduser().resolve()
            for root in allowed_roots:
                try:
                    candidate.relative_to(root)
                    return str(candidate)
                except ValueError:
                    continue
            raise ValueError(
                f"working_dir {requested!r} is not inside any configured codebase. "
                f"Allowed roots: {[str(r) for r in allowed_roots]}"
            )

        return self._pick_working_dir(task)

    def _pick_working_dir(self, task: Task) -> str:
        """Match ticket title/body against configured codebases by keyword.

        Simple heuristic: count how many codebase keys or known keywords appear
        in the task text, pick the highest scorer. Falls back to first codebase.
        """
        if not self.cfg.codebases:
            raise ValueError("No codebases configured")
        if len(self.cfg.codebases) == 1:
            return str(Path(self.cfg.codebases[0].path).expanduser().resolve())

        text = f"{task.title} {task.description} {task.board}".lower()
        scores = {}
        for cb in self.cfg.codebases:
            score = 0
            key = cb.key.lower()
            if key in text:
                score += 5
            # Repo name heuristic
            path_name = Path(cb.path).name.lower()
            if path_name != key and path_name in text:
                score += 3
            scores[cb.key] = score

        best = max(scores.items(), key=lambda x: x[1])
        if best[1] == 0:
            return str(Path(self.cfg.codebases[0].path).expanduser().resolve())
        picked = next(c for c in self.cfg.codebases if c.key == best[0])
        return str(Path(picked.path).expanduser().resolve())

    async def _run(self, session_id: str, task: Task, wd: str, mode: str) -> None:
        session = self._sessions[session_id]
        try:
            icpg_ctx = await self._build_icpg_context(task, wd)
            if mode == "plan":
                await self._run_plan(session, task, wd, icpg_ctx)
                return
            await self._run_tdd(session, task, wd, icpg_ctx)
        except Exception as e:
            logger.exception("Execution failed")
            session["status"] = "failed"
            session["error"] = str(e)
        finally:
            self._locks.release_all(session_id)
            cp_id = task.id.replace("/", "-")
            self._checkpoint.delete(cp_id)

    async def _run_plan(
        self, session: dict, task: Task, wd: str, icpg_ctx: str,
    ) -> None:
        result = await self._run_model(
            task, self._plan_prompt(task, icpg_ctx), wd, 5,
        )
        session["output"] = result.output[:10000]
        session["status"] = "completed" if result.success else "failed"
        if not result.success:
            session["error"] = result.output[:500]
            return
        if result.output:
            await self._post_plan(task.id, result.output)

    async def _run_tdd(
        self, session: dict, task: Task, wd: str, icpg_ctx: str,
    ) -> None:
        blast = self._blast_score(task)
        if blast >= 7:
            await self._dual_plan(session, task, wd)
        ok, analysis = await self._run_step(
            session, "ANALYZE", self._analysis_prompt(task, icpg_ctx),
            task, wd, 5,
        )
        if not ok:
            session["error"] = f"Analyze step failed: {analysis[:300]}"
            return
        ok, output = await self._run_step(
            session, "WRITE TESTS", self._tests_prompt(task, icpg_ctx, analysis),
            task, wd, 15,
        )
        if not ok:
            session["error"] = f"Write-tests step failed: {output[:300]}"
            return
        await self._save_rollback(session["id"], wd)
        ok, output = await self._run_step(
            session, "IMPLEMENT", self._impl_prompt(task, icpg_ctx),
            task, wd, 25,
        )
        if not ok:
            await self._try_rollback(session["id"], wd)
            self._maybe_escalate(session, task)
            return
        session["status"] = "completed"
        session["completed_at"] = datetime.now(timezone.utc).isoformat()

    async def _run_step(
        self,
        session: dict,
        label: str,
        prompt: str,
        task: Task,
        wd: str,
        max_turns: int,
    ) -> tuple[bool, str]:
        result = await self._run_model(task, prompt, wd, max_turns)
        session["output"] += f"\n=== {label} ===\n{result.output[:2000]}\n"
        self._log_signal(session["id"], label, result)
        if not result.success:
            session["status"] = "failed"
        return result.success, result.output

    async def _run_model(
        self, task: Task, prompt: str, wd: str, max_turns: int,
    ) -> RunResult:
        decision = self._route_model(task)
        model_name = self._model_name(decision.primary)
        self._write_checkpoint(task, model_name)
        result = await self._pi.send_with_fallback(
            model_name, prompt, wd, max_turns,
        )
        if result.model != model_name:
            model_entry = self._pi.get_model(result.model)
            if model_entry:
                self._fatigue.on_model_switch(model_entry.context_window)
        self._track_fatigue(result)
        if result.cost_usd > 0:
            self._budget.record_spend(
                decision.primary.provider,
                result.model,
                result.cost_usd,
            )
        return result

    def _route_model(self, task: Task) -> RoutingDecision:
        raw = task.raw if isinstance(task.raw, dict) else {}
        task_type = str(raw.get("task_type") or self._task_type(task))
        return self._routing.route(
            RoutingContext(
                blast_score=self._int_value(raw.get("blast_score")),
                task_type=task_type,
                security_sensitive=self._security_flag(raw, task_type),
                project_key=str(raw.get("project_key") or task.board),
            )
        )

    def _task_type(self, task: Task) -> str:
        if task.labels:
            return task.labels[0]
        return "general"

    def _security_flag(
        self, raw: dict[str, object], task_type: str,
    ) -> bool:
        if "security_sensitive" in raw:
            return bool(raw["security_sensitive"])
        return task_type in {"security", "auth", "billing"}

    def _blast_score(self, task: Task) -> int:
        raw = task.raw if isinstance(task.raw, dict) else {}
        return self._int_value(raw.get("blast_score"))

    def _int_value(self, value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _model_name(self, primary: object) -> str:
        if isinstance(primary, str):
            return primary
        return str(primary.name)

    async def _dual_plan(self, session: dict, task: Task, wd: str) -> None:
        try:
            result = await self._planner.dual_plan(
                task.title, task.description[:1500], wd,
            )
            session["dual_plan"] = result.primary_plan[:2000]
            if result.conflicts:
                session["plan_conflicts"] = result.conflicts
        except Exception as exc:
            logger.warning("DualPlanner failed: %s", exc)

    async def _save_rollback(self, sid: str, wd: str) -> None:
        try:
            await self._rollback.create_savepoint(sid, wd)
        except Exception as exc:
            logger.warning("Savepoint failed: %s", exc)

    async def _try_rollback(self, sid: str, wd: str) -> None:
        try:
            await self._rollback.rollback(sid, wd)
        except Exception as exc:
            logger.warning("Rollback failed: %s", exc)

    def _maybe_escalate(self, session: dict, task: Task) -> None:
        failures = session.get("_fail_count", 0) + 1
        session["_fail_count"] = failures
        if failures >= 3:
            self._escalator.escalate(
                session["id"], "repeated_failure",
                {"task_id": task.id, "failures": failures},
            )

    def _track_fatigue(self, result: RunResult) -> None:
        load = min(len(result.output) / 50_000, 1.0)
        self._fatigue.record("context_load", load)

    def _log_signal(self, sid: str, label: str, result: RunResult) -> None:
        self._signals.append({
            "session_id": sid, "step": label,
            "model": result.model, "success": result.success,
        })

    def _write_checkpoint(self, task: Task, model: str) -> None:
        self._checkpoint.write(task.id.replace("/", "-"), {
            "goal": task.title,
            "model_history": [model],
            "current_subgoal": "executing",
        })

    def _plan_prompt(self, task: Task, icpg_ctx: str) -> str:
        return (
            "Create an implementation plan for this ticket. No code changes — just a plan.\n\n"
            f"Ticket: {task.title}\n{task.description[:1500]}"
            f"{self._icpg_block(icpg_ctx)}\n"
            "Output: numbered steps, files to touch, risks, tests to add."
        )

    def _analysis_prompt(self, task: Task, icpg_ctx: str) -> str:
        return (
            "Analyze this ticket against the codebase and output a concise plan.\n"
            "Identify: files to change, functions affected, tests needed, risks.\n\n"
            f"Ticket: {task.title}\n{task.description[:1500]}"
            f"{self._icpg_block(icpg_ctx)}"
        )

    def _tests_prompt(self, task: Task, icpg_ctx: str, analysis: str) -> str:
        return (
            "Write failing test cases for this ticket (TDD — no implementation yet).\n"
            "Use the project's existing test patterns. Commit tests separately.\n\n"
            f"Ticket: {task.title}\n{task.description[:1500]}"
            f"{self._icpg_block(icpg_ctx)}\n"
            f"Analysis:\n{analysis[:1000]}"
        )

    def _impl_prompt(self, task: Task, icpg_ctx: str) -> str:
        return (
            "Implement the feature to make the failing tests pass.\n"
            "Follow existing code patterns. Keep changes minimal.\n\n"
            f"Ticket: {task.title}\n{task.description[:1500]}"
            f"{self._icpg_block(icpg_ctx)}\n"
            "Run tests to verify, then commit with a conventional commit message."
        )

    def _icpg_block(self, icpg_ctx: str) -> str:
        if not icpg_ctx:
            return ""
        return f"\n\n{icpg_ctx}\n"

    async def _post_plan(self, task_id: str, output: str) -> None:
        try:
            await self.provider.add_comment(
                task_id, f"## Maggy Plan\n\n{output[:4000]}",
            )
        except Exception as e:
            logger.warning("Failed to post plan: %s", e)

    async def _build_icpg_context(self, task: Task, wd: str) -> str:
        """Query Maggy's iCPG CLI for symbols/blast radius/prior intents.

        Silent fallback if iCPG isn't installed or repo isn't indexed — returns empty string.

        Invokes the iCPG package (`python3 -m scripts.icpg`) which is a real CLI
        entry point with an argparse subcommand interface (init/create/record/query/
        drift/bootstrap/status). We use `query --subcommand prior --text <keywords>`
        to find relevant symbols and past intents. The scripts.icpg.symbols
        submodule is a utility module with NO __main__ — invoking it directly
        produces nothing.
        """
        bootstrap_path = self.cfg.resolve_bootstrap_path()
        if not bootstrap_path:
            return ""

        icpg_pkg = bootstrap_path / "scripts" / "icpg" / "__main__.py"
        if not icpg_pkg.exists():
            return ""

        keywords = self._extract_keywords(f"{task.title} {task.description}")
        if not keywords:
            return ""

        # Build one search text from the top keywords — iCPG's 'query prior' takes
        # a free-text query, not a keyword list.
        query_text = " ".join(keywords[:8])
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", "-m", "scripts.icpg",
                "--project", str(bootstrap_path),
                "query", "prior",
                "--text", query_text,
                "--limit", "8",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(bootstrap_path),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode != 0:
                return ""
            text = (stdout or b"").decode("utf-8", errors="replace").strip()
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            return ""

        if not text:
            return ""

        return (
            "## iCPG Code Intelligence\n"
            "Pre-queried from Maggy's intent code property graph:\n\n"
            + text[:2000]
            + "\n\n**Use this to target your file reads and avoid searching blind.**"
        )

    STOP = {"the", "and", "for", "to", "in", "of", "a", "is", "with", "on", "from",
            "be", "as", "by", "an", "or", "not", "all", "that", "this", "are", "can",
            "should", "would", "when", "how", "what", "where", "which", "we", "need",
            "also", "been", "has", "have", "it", "its", "new", "add", "fix", "update",
            "create", "delete", "get", "set", "use"}

    def _extract_keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
        keywords: list[str] = []
        seen: set[str] = set()
        for w in words:
            if w in self.STOP or len(w) < 3:
                continue
            if w in seen:
                continue
            seen.add(w)
            keywords.append(w)
        return keywords[:20]

    async def _run_claude(self, prompt: str, working_dir: str, max_turns: int = 20) -> tuple[bool, str]:
        """Spawn claude -p as a non-interactive subprocess on the user's local machine.

        Uses --dangerously-skip-permissions because (a) there's no terminal to
        answer permission prompts, and (b) the user explicitly authorized this
        execution by clicking Execute on the ticket.

        Returns (success, output). success=False on timeout, non-zero exit, or
        missing binary. Caller is responsible for flipping the session status
        to 'failed' when success=False — this function never silently masks
        a failed run as completed.
        """
        cmd = [
            CLAUDE_BIN,
            "-p", prompt,
            "--output-format", "text",
            "--max-turns", str(max_turns),
            "--dangerously-skip-permissions",
        ]
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
            text = (stdout or b"").decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return False, f"claude exited with status {proc.returncode}\n{text}"
            return True, text
        except asyncio.TimeoutError:
            # Kill the subprocess — wait_for alone doesn't terminate it.
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            return False, "claude timed out after 10 minutes (process terminated)"
        except FileNotFoundError:
            return False, "`claude` CLI not found on PATH. Install Claude Code first."
        except Exception as e:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            return False, f"claude subprocess error: {e}"
