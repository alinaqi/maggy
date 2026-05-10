"""AmnesiaProfile — 7-dimension memory diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from .store import EngramStore


@dataclass
class AmnesiaProfile:
    """7-dimension memory health assessment."""

    total_memories: int = 0
    active_count: int = 0
    superseded_count: int = 0
    facts: int = 0
    decisions: int = 0
    code_refs: int = 0
    handoffs: int = 0

    @property
    def health_score(self) -> float:
        """0.0-1.0 overall memory health."""
        if self.total_memories == 0:
            return 0.0
        active_ratio = self.active_count / self.total_memories
        diversity = sum(
            1 for c in [
                self.facts, self.decisions,
                self.code_refs, self.handoffs,
            ] if c > 0
        ) / 4.0
        return round(
            active_ratio * 0.6 + diversity * 0.4, 3,
        )


def diagnose(
    store: EngramStore, namespace: str | None = None,
) -> AmnesiaProfile:
    """Run diagnostics on memory store."""
    all_records = store.query(
        namespace=namespace, active_only=False, limit=10000,
    )
    active = [r for r in all_records if r.is_active]

    return AmnesiaProfile(
        total_memories=len(all_records),
        active_count=len(active),
        superseded_count=len(all_records) - len(active),
        facts=sum(1 for r in active if r.memory_type == "fact"),
        decisions=sum(
            1 for r in active if r.memory_type == "decision"
        ),
        code_refs=sum(
            1 for r in active if r.memory_type == "code_ref"
        ),
        handoffs=sum(
            1 for r in active if r.memory_type == "handoff"
        ),
    )
