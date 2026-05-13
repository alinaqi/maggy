"""Routed chat — blast-score routing for interactive messages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from maggy.routing import RoutingContext

HIGH_KEYWORDS = frozenset({"security", "auth", "authentication", "authorization", "oauth", "encrypt", "vulnerability", "architecture", "refactor", "redesign", "migrate", "migration", "database", "schema", "performance", "optimize", "deploy", "infrastructure", "cicd", "pipeline"})
MID_KEYWORDS = frozenset({"feature", "implement", "build", "create", "api", "endpoint", "component", "service", "integration", "pagination", "filter", "search", "cache"})
LOW_KEYWORDS = frozenset({"fix", "typo", "rename", "move", "style", "format", "lint", "comment", "readme", "docs", "log", "print", "bump", "version", "config", "env", "update"})
TYPE_KEYWORDS: dict[str, frozenset[str]] = {
    "review": frozenset({"review", "code_review", "pr", "pullrequest", "audit", "inspect", "validate", "verify"}),
    "security": frozenset({"auth", "authentication", "authorization", "security", "permission", "token", "encrypt", "vulnerability", "oauth", "csrf"}),
    "search": frozenset({"find", "search", "grep", "where", "locate", "which", "look", "scan", "show", "list", "read"}),
    "docs": frozenset({"document", "documentation", "readme", "docs", "docstring", "comment", "spec", "jsdoc", "write"}),
    "tests": frozenset({"test", "spec", "coverage", "mock", "fixture", "assert", "pytest", "jest", "vitest"}),
    "frontend": frozenset({"component", "css", "style", "ui", "layout", "responsive", "tailwind", "react", "vue"}),
}
DEFAULT_BLAST = 5
_RETRIEVAL = re.compile(
    r"\b(find|get|show|check|where|list|read|look|grab|pick)\b",
    re.IGNORECASE,
)
_MUTATION = re.compile(
    r"\b(create|add|build|implement|write|refactor|migrate"
    r"|redesign|overhaul|deploy)\b",
    re.IGNORECASE,
)


_FORCE_RE = re.compile(
    r"\buse\s+(claude|codex|kimi|local)\b", re.IGNORECASE,
)


def parse_model_force(message: str) -> tuple[str, str | None]:
    """Extract 'use claude/codex/kimi/local' from message.

    Returns (cleaned_message, forced_model_or_None).
    """
    m = _FORCE_RE.search(message)
    if not m:
        return message, None
    model = m.group(1).lower()
    cleaned = (message[:m.start()] + message[m.end():]).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, model


def estimate_blast(message: str) -> int:
    """Estimate blast score (1-10) from message text."""
    if not message.strip():
        return DEFAULT_BLAST
    words = set(re.findall(r"[a-zA-Z]+", message.lower()))
    has_kw = words & (HIGH_KEYWORDS | MID_KEYWORDS | LOW_KEYWORDS)
    if len(words) <= 3 and not has_kw:
        return 1
    high = len(words & HIGH_KEYWORDS)
    mid = len(words & MID_KEYWORDS)
    low = len(words & LOW_KEYWORDS)
    score = _keyword_score(high, mid, low)
    return _apply_intent(message, score)


def _keyword_score(high: int, mid: int, low: int) -> int:
    """Score based on keyword tier counts."""
    if high >= 2:
        return min(9, 7 + high - 2)
    if high == 1:
        return 7
    if low >= 2 and mid == 0:
        return 2
    if low >= 1 and mid == 0:
        return 3
    if mid >= 2:
        return 6
    if mid >= 1:
        return 5
    return 1


def _apply_intent(message: str, score: int) -> int:
    """Cap score for retrieval-only messages."""
    is_retrieval = bool(_RETRIEVAL.search(message))
    is_mutation = bool(_MUTATION.search(message))
    if is_retrieval and not is_mutation and score < 7:
        return min(score, 3)
    return score


def estimate_type(message: str) -> str:
    """Estimate task type from message keywords."""
    words = set(re.findall(r"[a-zA-Z]+", message.lower()))
    best_type = "general"
    best_count = 0
    for ttype, keywords in TYPE_KEYWORDS.items():
        count = len(words & keywords)
        if count > best_count:
            best_count = count
            best_type = ttype
    return best_type


@dataclass
class RouteDecision:
    """Result of routing a chat message."""

    model: str
    reason: str
    blast: int
    task_type: str
    blueprint_context: str = ""


class RoutedChat:
    """Routes chat messages through blast-score engine."""

    def __init__(
        self, routing, budget,
        blueprints=None, project_key: str = "",
    ):
        self._routing = routing
        self._budget = budget
        self._blueprints = blueprints
        self._project_key = project_key

    async def decide(
        self,
        message: str,
        blast_override: int | None = None,
        type_override: str | None = None,
    ) -> RouteDecision:
        """Get routing decision for a message.

        Uses semantic classification via local Ollama model.
        Supports inline model forcing: 'use claude/codex/kimi/local'.
        """
        cleaned, forced = parse_model_force(message)
        from maggy.services.intent_classifier import (
            classify_blast,
            classify_intent,
        )
        if blast_override:
            blast = blast_override
        else:
            blast = await classify_blast(cleaned)
        if type_override:
            task_type = type_override
        else:
            task_type = await classify_intent(cleaned)
        if forced:
            return RouteDecision(
                model=forced,
                reason=f"user forced '{forced}'",
                blast=blast,
                task_type=task_type,
            )
        bp_match = self._match_blueprint(cleaned, task_type)
        if bp_match:
            return bp_match
        ctx = RoutingContext(
            blast_score=blast, task_type=task_type,
        )
        decision = self._routing.route(ctx)
        model_name = self._model_name(decision.primary)
        return RouteDecision(
            model=model_name,
            reason=decision.reason,
            blast=blast,
            task_type=task_type,
        )

    def _match_blueprint(self, msg: str, task_type: str):
        """Return RouteDecision if blueprint matches."""
        if not self._blueprints:
            return None
        from maggy.blueprint_extract import (
            build_context,
            extract_keywords,
        )
        kw = extract_keywords(msg)
        bp = self._blueprints.match(
            task_type, kw, self._project_key,
        )
        if not bp:
            return None
        return RouteDecision(
            model=bp["min_model"],
            reason=f"blueprint:{bp['fingerprint'][:8]}",
            blast=0,
            task_type=task_type,
            blueprint_context=build_context(bp),
        )

    def _model_name(self, primary) -> str:
        if isinstance(primary, str):
            return primary
        return str(getattr(primary, "name", primary))
