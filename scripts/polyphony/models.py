"""Data models for Polyphony (spec §3)."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Task types (§5.1) ---
TASK_TYPES = (
    "research", "bugfix", "feature", "refactor",
    "migration", "docs", "review",
)

# --- Risk levels (§5.1) ---
RISK_LEVELS = ("low", "medium", "high")

# --- Scope levels (§5.1) ---
SCOPES = (
    "single_file", "single_module",
    "multi_module", "multi_repo",
)

# --- Result statuses ---
RESULT_STATUSES = (
    "succeeded", "failed", "quota", "timeout", "crash",
)


@dataclass
class Task:
    """A unit of work from a work source (§3.1)."""

    title: str
    source: str
    source_ref: str
    id: str = field(default_factory=_uuid)
    state: str = "discovered"
    task_type: str = "feature"
    scope: list[str] = field(default_factory=list)
    risk: str = "low"
    context_tokens: int = 0
    requires_web: bool = False
    run_spec_id: str | None = None
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Identity:
    """Named credential bundle (§3.2)."""

    name: str
    volumes: dict[str, str] = field(default_factory=dict)
    api_keys: dict[str, str] = field(default_factory=dict)
    cost_ceiling_usd_per_day: float | None = None


@dataclass
class AgentProfile:
    """Agent harness profile (§3.3)."""

    name: str
    agent_type: str
    cli_command: str
    context_window_tokens: int = 200000
    strengths: list[str] = field(default_factory=list)
    event_protocol: str = "ndjson"
    auth_path: str = ""


@dataclass
class RunSpec:
    """Immutable execution spec for one attempt (§3.4)."""

    task_id: str
    agent: str
    identity: str
    workspace: str
    image: str
    id: str = field(default_factory=_uuid)
    attempt: int = 1
    model: str = ""
    fallback: list[str] = field(default_factory=list)
    max_turns: int = 25
    allowed_paths: list[str] = field(default_factory=list)
    proof_of_work: list[str] = field(default_factory=list)
    env_overlay: dict[str, str] = field(default_factory=dict)
    volume_mounts: list[str] = field(default_factory=list)
    hooks_pre: list[str] = field(default_factory=list)
    hooks_post: list[str] = field(default_factory=list)
    deadline_seconds: int = 1800


@dataclass
class Result:
    """Outcome of a single run attempt (§3.5)."""

    task_id: str
    run_spec_id: str
    agent: str
    status: str
    id: str = field(default_factory=_uuid)
    turns: int = 0
    duration_seconds: int = 0
    cost_usd: float | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    completed_at: str = field(default_factory=_now)
