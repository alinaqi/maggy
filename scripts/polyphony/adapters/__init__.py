"""Agent adapters for Polyphony (§8).

Registry of adapter classes by agent_type name.
"""

from __future__ import annotations

from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .kimi import KimiAdapter

_REGISTRY: dict[str, type] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "kimi": KimiAdapter,
}


def get_adapter(agent_type: str):
    """Get adapter instance by agent type name."""
    cls = _REGISTRY.get(agent_type)
    if cls is None:
        raise KeyError(agent_type)
    return cls()


def list_adapters() -> list[str]:
    """Return registered adapter names."""
    return list(_REGISTRY.keys())
