"""Learning configuration — opt-in / opt-out per namespace."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LearningConfig:
    enabled: bool = True
    namespaces: dict[str, bool] = field(default_factory=lambda: {
        "chat-feedback": True,
        "review-feedback": True,
        "pr-feedback": True,
        "error-patterns": True,
    })
    max_per_namespace: int = 500

    def is_enabled(self, namespace: str) -> bool:
        return self.enabled and self.namespaces.get(namespace, False)
