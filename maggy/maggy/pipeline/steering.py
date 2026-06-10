"""Incomplete turn steering — detects advise-only, injects correction."""

from __future__ import annotations

_PLANNING_SIGNALS = [
    "here's what you should do",
    "here is what you should do",
    "you can try",
    "i recommend",
    "steps to follow",
    "you'll need to",
    "you will need to",
    "you should update",
    "you should change",
    "you need to",
]

_ACTION_SIGNALS = [
    "tool_call",
    "i've updated",
    "i have updated",
    "i've fixed",
    "i edited",
    "i wrote",
    "i created",
    "changes made",
    "tests pass",
    "all passing",
]


def needs_steering(response: str) -> bool:
    if not response.strip():
        return False
    lower = response.lower()
    for sig in _ACTION_SIGNALS:
        if sig in lower:
            return False
    for sig in _PLANNING_SIGNALS:
        if sig in lower:
            return True
    return False


def steering_injection() -> str:
    return (
        "Do not advise. Execute the plan directly using tools. "
        "Read files, edit code, run tests — do it yourself and "
        "report the result."
    )
