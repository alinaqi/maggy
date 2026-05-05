"""Work sources for Polyphony (§2).

Registry of task source implementations.
"""

from __future__ import annotations

from .local import LocalSource
from .github import GitHubSource

_REGISTRY: dict[str, type] = {
    "local": LocalSource,
    "github": GitHubSource,
}


def get_source(kind: str, **kwargs):
    """Get source instance by kind name."""
    cls = _REGISTRY.get(kind)
    if cls is None:
        raise KeyError(kind)
    return cls(**kwargs)


def list_sources() -> list[str]:
    """Return registered source names."""
    return list(_REGISTRY.keys())
