"""Telos data models — IntentNode, IFSScore, TelosResult."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _parse_json_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


@dataclass
class IntentNode:
    id: str
    goal: str
    owner: str
    status: str
    created_at: str
    decision_type: str = "task"
    scope: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    anti_criteria: list[str] = field(default_factory=list)
    parent_id: str | None = None
    fulfilled_at: str | None = None

    @property
    def has_contracts(self) -> bool:
        return bool(
            self.preconditions
            or self.postconditions
            or self.invariants
        )

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> IntentNode:
        return cls(
            id=row["id"],
            goal=row["goal"],
            owner=row["owner"],
            status=row["status"],
            created_at=row["created_at"],
            decision_type=row.get("decision_type", "task"),
            scope=_parse_json_list(row.get("scope")),
            preconditions=_parse_json_list(row.get("preconditions")),
            postconditions=_parse_json_list(row.get("postconditions")),
            invariants=_parse_json_list(row.get("invariants")),
            anti_criteria=_parse_json_list(row.get("anti_criteria")),
            parent_id=row.get("parent_id"),
            fulfilled_at=row.get("fulfilled_at"),
        )


@dataclass
class IFSScore:
    f1: float
    f2: float
    f3: float
    details: dict[str, Any] = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: (
        datetime.now(timezone.utc).isoformat()
    ))

    @property
    def composite(self) -> float:
        return self.f1 * self.f2 * self.f3


@dataclass
class TelosResult:
    project: str
    ifs: IFSScore
    test_results: dict[str, Any]
    drift_signals: list[dict[str, Any]]
    intent_bugs: list[str]
    anti_criteria_violations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "ifs": {
                "f1": self.ifs.f1,
                "f2": self.ifs.f2,
                "f3": self.ifs.f3,
                "composite": self.ifs.composite,
                "computed_at": self.ifs.computed_at,
            },
            "test_results": self.test_results,
            "drift_signals": self.drift_signals,
            "intent_bugs": self.intent_bugs,
            "anti_criteria_violations": (
                self.anti_criteria_violations
            ),
        }
