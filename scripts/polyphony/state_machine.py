"""Task state machine for Polyphony (spec §4)."""

from __future__ import annotations

from .models import Task, _now

TASK_STATES = (
    "discovered", "claimed", "routed", "provisioned",
    "running", "verifying", "landed", "failed", "blocked",
)

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "discovered": ("claimed",),
    "claimed": ("routed",),
    "routed": ("provisioned",),
    "provisioned": ("running",),
    "running": ("verifying", "failed"),
    "verifying": ("landed", "failed"),
    "failed": ("claimed", "blocked"),
}

TERMINAL_STATES = ("landed", "blocked")


def can_transition(current: str, target: str) -> bool:
    """Check if a state transition is valid."""
    allowed = TRANSITIONS.get(current, ())
    return target in allowed


def transition(task: Task, target: str) -> Task:
    """Transition a task to a new state. Raises on invalid."""
    if not can_transition(task.state, target):
        msg = f"Invalid transition: {task.state} -> {target}"
        raise ValueError(msg)
    task.state = target
    task.updated_at = _now()
    return task


def is_terminal(state: str) -> bool:
    """Check if a state is terminal (no further transitions)."""
    return state in TERMINAL_STATES
