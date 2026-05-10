"""Two-tier Lexon router — fast keyword + fallback LLM."""

from __future__ import annotations

from .disambiguate import disambiguate, DisambiguationResult
from .personalization import PersonalizationEngine
from .record import LexonRecord
from .terminology import TerminologyMap


class LexonRouter:
    """Routes user phrases to tools using two tiers.

    Tier 1: Fast keyword/terminology lookup
    Tier 2: LLM-based intent classification (stub)
    """

    def __init__(self):
        self._terms = TerminologyMap()
        self._personal = PersonalizationEngine()
        self._tool_map: dict[str, list[str]] = {
            "deploy": ["vercel_deploy", "docker_push"],
            "test": ["pytest", "vitest", "jest"],
            "fix": ["code_edit", "patch"],
            "create": ["file_create", "scaffold"],
            "delete": ["file_delete", "cleanup"],
            "update": ["code_edit", "config_update"],
            "search": ["grep", "glob", "find"],
            "review": ["code_review", "pr_review"],
        }

    def route(self, phrase: str) -> LexonRecord:
        """Route a phrase to a tool."""
        # Check personalization first
        preferred = self._personal.get_preferred(phrase)
        if preferred:
            return LexonRecord(
                phrase=phrase,
                resolved_tool=preferred,
                confidence=0.95,
                candidates=[preferred],
            )

        # Tier 1: keyword lookup
        words = phrase.lower().split()
        for word in words:
            canonical = self._terms.resolve(word)
            if canonical and canonical in self._tool_map:
                candidates = self._tool_map[canonical]
                confidence = 0.8 if len(candidates) == 1 else 0.6
                result = disambiguate(confidence, candidates)
                return LexonRecord(
                    phrase=phrase,
                    resolved_tool=result.tool if result.resolved else "",
                    confidence=confidence,
                    candidates=candidates,
                    disambiguation_mode=result.mode,
                )

        # Tier 2: LLM fallback (stub)
        return LexonRecord(
            phrase=phrase, confidence=0.2,
            disambiguation_mode="user_clarify",
        )

    def learn(self, phrase: str, tool: str) -> None:
        """Record a confirmed tool selection."""
        self._personal.record_use(tool)
        self._personal.record_alias(phrase, tool)

    @property
    def terminology(self) -> TerminologyMap:
        return self._terms

    @property
    def personalization(self) -> PersonalizationEngine:
        return self._personal
