"""Data models for Cortex structure layer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def symbol_id(file_path: str, name: str, symbol_type: str) -> str:
    raw = f"{file_path}:{name}:{symbol_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


SYMBOL_TYPES = (
    "function",
    "class",
    "module",
    "route",
    "schema",
    "component",
    "interface",
    "type",
    "constant",
    "hook",
    "method",
)


@dataclass
class Symbol:
    name: str
    file_path: str
    symbol_type: str
    language: str
    id: str = ""
    signature: str | None = None
    checksum: str = ""
    line_start: int | None = None
    line_end: int | None = None
    docstring: str | None = None
    complexity: int | None = None
    is_pinned: bool = False
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = symbol_id(self.file_path, self.name, self.symbol_type)
