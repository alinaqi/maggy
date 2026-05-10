"""skill_lint -- Quality gates for Maggy skills."""

from __future__ import annotations

__version__ = '0.1.0'

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    message: str
    line: int | None = None
    suggestion: str | None = None
