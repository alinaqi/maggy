"""5-dimension complexity scoring (spec §5.1).

Formalizes the cross-agent-delegation rubric:
  cyclomatic, fan_out, security, concurrency, domain
Each dimension scores 0-2. Total 0-10.
"""

from __future__ import annotations

from .models import Task

DIMENSIONS = (
    "cyclomatic", "fan_out", "security",
    "concurrency", "domain",
)

SEC_KEYWORDS = frozenset({
    "auth", "org_id", "user_id", "pii",
    "rls", "billing", "payment", "secret",
    "token", "session", "csrf", "xss",
})

CONCURRENCY_KEYWORDS = frozenset({
    "asyncio.lock", "for update", "transaction",
    "session.begin", "mutex", "semaphore",
    "atomic", "lock",
})


def score_task(task: Task) -> int:
    """Total complexity score (0-10)."""
    return (
        score_cyclomatic(task)
        + score_fan_out(task)
        + score_security(task)
        + score_concurrency(task)
        + score_domain(task)
    )


def score_cyclomatic(task: Task) -> int:
    """0-2 based on LOC and scope size."""
    loc = task.metadata.get("loc", 0)
    n_files = len(task.scope)
    if loc >= 50 or n_files >= 5:
        return 2
    if loc >= 10 or n_files >= 2:
        return 1
    return 0


def score_fan_out(task: Task) -> int:
    """0-2 based on number of callers."""
    callers = task.metadata.get("callers", 0)
    if callers >= 11:
        return 2
    if callers >= 3:
        return 1
    return 0


def score_security(task: Task) -> int:
    """0-2 based on security keyword presence."""
    keywords = _extract_keywords(task)
    hits = keywords & SEC_KEYWORDS
    if len(hits) >= 2:
        return 2
    if len(hits) >= 1:
        return 1
    return 0


def score_concurrency(task: Task) -> int:
    """0-2 based on concurrency keyword presence."""
    keywords = _extract_keywords(task)
    hits = keywords & CONCURRENCY_KEYWORDS
    if len(hits) >= 2:
        return 2
    if len(hits) >= 1:
        return 1
    return 0


def score_domain(task: Task) -> int:
    """0-2 based on risk + task type heuristic."""
    if task.risk == "high":
        return 2
    if task.risk == "medium" or task.task_type == "refactor":
        return 1
    return 0


def _extract_keywords(task: Task) -> set[str]:
    """Collect keywords from metadata and title."""
    kw = set()
    for k in task.metadata.get("keywords", []):
        kw.add(k.lower())
    for word in task.title.lower().split():
        kw.add(word)
    return kw
