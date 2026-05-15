"""Executor helpers — routing, rollback, fatigue, iCPG."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from maggy.adapters.pi import RunResult
from maggy.mnemos import FatigueTracker, SignalLog
from maggy.process.model_router import RoutingDecision
from maggy.routing import RoutingContext, RoutingService

if TYPE_CHECKING:
    from maggy.checkpoint import CheckpointManager
    from maggy.config import MaggyConfig
    from maggy.escalation.protocol import Escalator
    from maggy.providers.base import Task
    from maggy.recovery.rollback import RollbackManager

logger = logging.getLogger(__name__)


def route_model(
    task: Task, routing: RoutingService, fatigue_score: float = 0.0,
) -> RoutingDecision:
    """Pick the best model for a task via routing rules."""
    from maggy.services.stakes import classify_stakes

    raw = task.raw if isinstance(task.raw, dict) else {}
    task_type = str(raw.get("task_type") or _task_type(task))
    stakes = classify_stakes(task).level
    return routing.route(
        RoutingContext(
            blast_score=int_value(raw.get("blast_score")),
            task_type=task_type,
            security_sensitive=_security_flag(raw, task_type),
            project_key=str(raw.get("project_key") or task.board),
            stakes=stakes,
            fatigue_score=fatigue_score,
        ),
    )


def blast_score(task: Task) -> int:
    """Extract blast score from task metadata."""
    raw = task.raw if isinstance(task.raw, dict) else {}
    return int_value(raw.get("blast_score"))


def int_value(value: object) -> int:
    """Safely convert to int, default 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def model_name(primary: object) -> str:
    """Extract model name string from routing decision."""
    if isinstance(primary, str):
        return primary
    return str(primary.name)


def track_fatigue(fatigue: FatigueTracker, result: RunResult) -> None:
    """Record context load from result output length."""
    load = min(len(result.output) / 50_000, 1.0)
    fatigue.record("context_load", load)


def log_signal(signals: SignalLog, sid: str, label: str, result: RunResult) -> None:
    """Append step signal to log."""
    signals.append({
        "session_id": sid, "step": label,
        "model": result.model, "success": result.success,
    })


def write_checkpoint(
    checkpoint: "CheckpointManager", task: Task, model: str,
) -> None:
    """Write execution checkpoint for crash recovery."""
    checkpoint.write(task.id.replace("/", "-"), {
        "goal": task.title,
        "model_history": [model],
        "current_subgoal": "executing",
    })


async def save_rollback(
    rollback: "RollbackManager", sid: str, wd: str,
) -> None:
    """Create git savepoint before implementation."""
    try:
        await rollback.create_savepoint(sid, wd)
    except Exception as exc:
        logger.warning("Savepoint failed: %s", exc)


async def try_rollback(
    rollback: "RollbackManager", sid: str, wd: str,
) -> None:
    """Revert to last savepoint on failure."""
    try:
        await rollback.rollback(sid, wd)
    except Exception as exc:
        logger.warning("Rollback failed: %s", exc)


def maybe_escalate(
    escalator: "Escalator", session: dict, task: Task,
) -> None:
    """Escalate after 3+ consecutive failures."""
    failures = session.get("_fail_count", 0) + 1
    session["_fail_count"] = failures
    if failures >= 3:
        escalator.escalate(
            session["id"], "repeated_failure",
            {"task_id": task.id, "failures": failures},
        )


async def build_icpg_context(cfg: "MaggyConfig", task: Task) -> str:
    """Query iCPG CLI for code intelligence context."""
    bp = cfg.resolve_bootstrap_path()
    if not bp or not (bp / "scripts" / "icpg" / "__main__.py").exists():
        return ""
    from maggy.services.executor_prompts import extract_keywords
    kw = extract_keywords(f"{task.title} {task.description}")
    if not kw:
        return ""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "scripts.icpg", "--project", str(bp),
            "query", "prior", "--text", " ".join(kw[:8]), "--limit", "8",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(bp))
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return ""
        text = (stdout or b"").decode("utf-8", errors="replace").strip()
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return ""
    if not text:
        return ""
    return ("## iCPG Code Intelligence\n"
            "Pre-queried from Maggy's intent code property graph:\n\n"
            + text[:2000] + "\n\n**Use this to target your file reads.**")


def resolve_working_dir(cfg: "MaggyConfig", requested: str | None, task: "Task") -> str:
    """Resolve working_dir inside configured codebases."""
    from pathlib import Path
    if not cfg.codebases:
        raise ValueError("No codebases configured")
    roots = [Path(c.path).expanduser().resolve() for c in cfg.codebases]
    if requested:
        candidate = Path(requested).expanduser().resolve()
        for root in roots:
            try:
                candidate.relative_to(root)
                return str(candidate)
            except ValueError:
                continue
        raise ValueError(f"working_dir {requested!r} not inside codebases")
    return pick_working_dir(cfg, task)


def pick_working_dir(cfg: "MaggyConfig", task: "Task") -> str:
    """Match task keywords to configured codebases."""
    from pathlib import Path
    cbs = cfg.codebases
    if len(cbs) == 1:
        return str(Path(cbs[0].path).expanduser().resolve())
    text = f"{task.title} {task.description} {task.board}".lower()
    best_key, best_score = cbs[0].key, 0
    for cb in cbs:
        score = 5 if cb.key.lower() in text else 0
        name = Path(cb.path).name.lower()
        if name != cb.key.lower() and name in text:
            score += 3
        if score > best_score:
            best_key, best_score = cb.key, score
    picked = next(c for c in cbs if c.key == best_key)
    return str(Path(picked.path).expanduser().resolve())


async def post_plan(provider, task_id: str, output: str) -> None:
    """Post plan as comment to issue tracker."""
    try:
        await provider.add_comment(
            task_id, f"## Maggy Plan\n\n{output[:4000]}",
        )
    except Exception as e:
        logger.warning("Failed to post plan: %s", e)


def _task_type(task: "Task") -> str:
    return task.labels[0] if task.labels else "general"


def select_strategy(
    blast: int, file_count: int, fatigue: float = 0.0,
) -> str:
    """Return 'parallel' or 'sequential' execution strategy."""
    from maggy.mnemos.constants import FATIGUE_PARALLEL_BLOCK
    if fatigue >= FATIGUE_PARALLEL_BLOCK:
        return "sequential"
    if blast >= 7 or file_count >= 5:
        return "parallel"
    return "sequential"


def _security_flag(raw: dict, task_type: str) -> bool:
    if "security_sensitive" in raw:
        return bool(raw["security_sensitive"])
    return task_type in {"security", "auth", "billing"}
