"""Protocol data models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProtocolStep:
    name: str
    label: str
    cmd: str
    optional: bool = False
    condition: str = ""
    requires: str = ""


@dataclass
class Protocol:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    steps: list[ProtocolStep] = field(default_factory=list)

    def matches(self, message: str) -> bool:
        lower = message.lower()
        return any(t.lower() in lower for t in self.triggers)
