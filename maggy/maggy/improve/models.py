"""Data models for self-improvement analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recommendation:
    category: str   # routing | reliability | usage | capability | memory | cost
    severity: str   # info | warning | action
    message: str
    suggestion: str
    data: dict = field(default_factory=dict)


@dataclass
class SignalBundle:
    routing: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)
    history: dict = field(default_factory=dict)
    forge: dict = field(default_factory=dict)
    engram: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    collected_at: str = ""


@dataclass
class ImprovementReport:
    generated_at: str
    total_signals: int
    recommendations: list[Recommendation] = field(default_factory=list)
    health_summary: dict = field(default_factory=dict)
    top_actions: list[str] = field(default_factory=list)
