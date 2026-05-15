"""Progress analysis engine — cross-model tracking, auto-adjust, next-action suggestions.

Watches execution across model tiers, detects blockers, adjusts routing,
and suggests next actions based on project state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProgressSnapshot:
    project_key: str
    active_tasks: list[dict] = field(default_factory=list)
    completed_tasks: list[dict] = field(default_factory=list)
    blocked_tasks: list[dict] = field(default_factory=list)
    model_usage: dict[str, int] = field(default_factory=dict)
    fatigue_score: float = 0.0
    elapsed_seconds: float = 0.0
    suggested_next: list[str] = field(default_factory=list)
    auto_adjustments: list[str] = field(default_factory=list)


class ProgressEngine:
    """Tracks multi-model execution and suggests adjustments."""

    def __init__(self, project_key: str = ""):
        self._project_key = project_key
        self._start_time = datetime.now(timezone.utc)
        self._history: list[dict] = []
        self._blockers: list[dict] = []
        self._model_stats: dict[str, int] = {}

    def record_step(self, model: str, step: str, status: str,
                    detail: str = "", cost_usd: float = 0.0) -> None:
        """Record an execution step."""
        self._model_stats[model] = self._model_stats.get(model, 0) + 1
        self._history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "step": step,
            "status": status,
            "detail": detail[:500],
            "cost_usd": cost_usd,
        })
        if status == "blocked":
            self._blockers.append(self._history[-1])

    def record_blocker(self, model: str, reason: str) -> None:
        """Record a blocker that needs resolution."""
        self._blockers.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "reason": reason,
        })
        logger.warning("Progress blocked on %s: %s", model, reason)

    def suggest_next_actions(self) -> list[str]:
        """Suggest next actions based on current state."""
        suggestions = []
        if self._blockers:
            suggestions.append(
                f"Resolve {len(self._blockers)} blocker(s) before continuing"
            )
            for b in self._blockers[-3:]:
                suggestions.append(
                    f"  Blocked on {b.get('model', 'unknown')}: {b.get('reason', 'unknown')}"
                )
        # Suggest model escalation if same model failed 2+ times
        for model, count in self._model_stats.items():
            fails = sum(
                1 for h in self._history[-10:]
                if h["model"] == model and h["status"] == "failed"
            )
            if fails >= 2:
                suggestions.append(
                    f"Consider switching from {model} — {fails} recent failures"
                )
        if not suggestions:
            # Check for unvalidated completions
            completions = [
                h for h in self._history
                if h["status"] == "completed" and h["step"] not in (
                    "VALIDATE", "GREEN"
                )
            ]
            if completions:
                suggestions.append(
                    f"Validate {len(completions)} completed step(s) "
                    f"before proceeding"
                )
            else:
                suggestions.append("All clear — pick next task from inbox")
        return suggestions

    def should_adjust_model(self, current_model: str,
                            fatigue: float = 0.0) -> tuple[bool, str]:
        """Decide if model tier should be adjusted."""
        if fatigue >= 0.75:
            return True, "Fatigue at REM level — escalate to premium model"
        if fatigue >= 0.60:
            return True, "Fatigue at PRE_SLEEP — consider simpler model"
        # Check recent failure rate
        recent = [h for h in self._history[-5:] if h["model"] == current_model]
        if recent and all(r["status"] == "failed" for r in recent):
            return True, f"{current_model} has 5 consecutive failures — escalate"
        return False, ""

    def snapshot(self, fatigue: float = 0.0) -> ProgressSnapshot:
        """Generate a progress snapshot."""
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        adjust, adjust_reason = self.should_adjust_model("", fatigue)

        return ProgressSnapshot(
            project_key=self._project_key,
            active_tasks=[h for h in self._history if h["status"] == "running"],
            completed_tasks=[
                h for h in self._history if h["status"] == "completed"
            ],
            blocked_tasks=self._blockers,
            model_usage=dict(self._model_stats),
            fatigue_score=fatigue,
            elapsed_seconds=elapsed,
            suggested_next=self.suggest_next_actions(),
            auto_adjustments=[adjust_reason] if adjust else [],
        )


def read_project_specs(project_dir: str) -> dict:
    """Read tasks from _project_specs/todos/ directory."""
    spec_dir = Path(project_dir) / "_project_specs" / "todos"
    if not spec_dir.exists():
        return {"tasks": [], "source": "_project_specs", "error": "not found"}

    tasks = []
    for todo_file in ["active.md", "backlog.md"]:
        path = spec_dir / todo_file
        if path.exists():
            content = path.read_text()
            # Parse markdown list items as tasks
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- [") or line.startswith("- "):
                    title = line.lstrip("- [ ]").lstrip("- [x]").lstrip("- ").strip()[:120]
                    status = "done" if "[x]" in line[:5] else "pending"
                    tasks.append({
                        "id": f"specs-{len(tasks)}",
                        "title": title,
                        "status": status,
                        "source": f"_project_specs/todos/{todo_file}",
                        "url": str(path),
                    })

    return {"tasks": tasks, "source": "_project_specs"}
