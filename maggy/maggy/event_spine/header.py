"""Common EventHeader shared by all typed events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EventHeader:
    """Standard fields for every event in the spine."""

    event_type: str
    event_id: str = field(default_factory=_uuid)
    task_id: str = ""
    project_id: str = ""
    agent_id: str = ""
    model_id: str = ""
    parent_event_id: str = ""
    confidence: float = 1.0
    namespace: str = ""
    policy_version: str = ""
    reward_delta: float = 0.0
    timestamp: str = field(default_factory=_now)
    schema_version: int = 1
