"""Executor prompt templates for TDD pipeline steps."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.providers.base import Task
    from maggy.routing import RoutingService

from maggy.routing_rules import conventions_for

STOP = frozenset({
    "the", "and", "for", "to", "in", "of", "a", "is", "with",
    "on", "from", "be", "as", "by", "an", "or", "not", "all",
    "that", "this", "are", "can", "should", "would", "when",
    "how", "what", "where", "which", "we", "need", "also",
    "been", "has", "have", "it", "its", "new", "add", "fix",
    "update", "create", "delete", "get", "set", "use",
})


def plan_prompt(task: Task, icpg_ctx: str, routing: RoutingService) -> str:
    conv = _conventions_block(task, routing)
    return (
        "Create an implementation plan for this ticket. "
        "No code changes — just a plan.\n\n"
        f"Ticket: {task.title}\n{task.description[:1500]}"
        f"{_icpg_block(icpg_ctx)}{conv}\n"
        "Output: numbered steps, files to touch, risks, tests."
    )


def analysis_prompt(task: Task, icpg_ctx: str, routing: RoutingService) -> str:
    conv = _conventions_block(task, routing)
    return (
        "Analyze this ticket against the codebase and output "
        "a concise plan.\nIdentify: files to change, functions "
        "affected, tests needed, risks.\n\n"
        f"Ticket: {task.title}\n{task.description[:1500]}"
        f"{_icpg_block(icpg_ctx)}{conv}"
    )


def tests_prompt(
    task: Task, icpg_ctx: str, analysis: str, routing: RoutingService,
) -> str:
    conv = _conventions_block(task, routing)
    return (
        "Write failing test cases for this ticket "
        "(TDD — no implementation yet).\n"
        "Use the project's existing test patterns. "
        "Commit tests separately.\n\n"
        f"Ticket: {task.title}\n{task.description[:1500]}"
        f"{_icpg_block(icpg_ctx)}{conv}\n"
        f"Analysis:\n{analysis[:1000]}"
    )


def impl_prompt(task: Task, icpg_ctx: str, routing: RoutingService) -> str:
    conv = _conventions_block(task, routing)
    return (
        "Implement the feature to make the failing tests pass.\n"
        "Follow existing code patterns. Keep changes minimal.\n\n"
        f"Ticket: {task.title}\n{task.description[:1500]}"
        f"{_icpg_block(icpg_ctx)}{conv}\n"
        "Run tests to verify, then commit with a conventional "
        "commit message."
    )


def extract_keywords(text: str) -> list[str]:
    """Extract unique keywords from text, filtering stop words."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        if w in STOP or len(w) < 3 or w in seen:
            continue
        seen.add(w)
        result.append(w)
    return result[:20]


def _icpg_block(icpg_ctx: str) -> str:
    if not icpg_ctx:
        return ""
    return f"\n\n{icpg_ctx}\n"


def _task_type(task: Task) -> str:
    if task.labels:
        return task.labels[0]
    return "general"


def _conventions_block(task: Task, routing: RoutingService) -> str:
    raw = task.raw if isinstance(task.raw, dict) else {}
    task_type = str(raw.get("task_type") or _task_type(task))
    project_key = str(raw.get("project_key") or "")
    text = conventions_for(routing.rules, task_type, project_key or None)
    if not text:
        return ""
    return f"\n\n{text}\n"
