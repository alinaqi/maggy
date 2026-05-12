"""Seed engrams on first boot for non-zero health."""

from __future__ import annotations

from .record import EngramRecord
from .store import EngramStore

_SEEDS = [
    ("seed-fact-1", "fact", "Maggy uses blast-score routing "
     "to pick the optimal model per task."),
    ("seed-fact-2", "fact", "Quality gates: max 20 lines/fn, "
     "3 params, 2 nesting, 200 lines/file."),
    ("seed-decision-1", "decision", "TDD workflow: RED "
     "(failing tests) -> GREEN (pass) -> VALIDATE."),
    ("seed-decision-2", "decision", "Local Qwen3-Coder "
     "handles blast 0-5; Claude handles 5-10."),
    ("seed-coderef-1", "code_ref",
     "Routing tiers: process/model_router.py DEFAULT_TIERS"),
    ("seed-coderef-2", "code_ref",
     "Chat REPL: cli_chat.py _repl_loop"),
    ("seed-handoff-1", "handoff", "System initialized. "
     "Memory will grow as tasks are completed."),
]

_REQUIRED_TYPES = {"fact", "decision", "code_ref", "handoff"}


def seed_if_empty(store: EngramStore) -> None:
    """Seed missing memory types for healthy diversity."""
    existing = {
        r.memory_type
        for r in store.query(active_only=True, limit=500)
    }
    missing = _REQUIRED_TYPES - existing
    if not missing:
        return
    for eid, mtype, content in _SEEDS:
        if mtype in missing:
            store.write(EngramRecord(
                engram_id=eid,
                namespace="system",
                memory_type=mtype,
                content=content,
                tags=["seed"],
            ))
