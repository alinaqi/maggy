"""Pydantic models for Mnemos memory nodes and state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from maggy.mnemos.constants import (
    CHECKPOINT_THRESHOLD,
    LINK_RELATED,
    NODE_TYPES,
    STATE_BOUNDARIES,
    STATUS_ACTIVE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid4().hex[:12]


class MnemoNode(BaseModel):
    """A typed memory node in the MnemoGraph."""

    id: str = Field(default_factory=_uuid)
    type: str
    task_id: str
    parent_node_id: str | None = None
    content: str
    summary: str | None = None
    activation_weight: float = 1.0
    created_at: datetime = Field(default_factory=_now)
    last_accessed: datetime = Field(default_factory=_now)
    access_count: int = 0
    status: str = STATUS_ACTIVE
    origin: str = "AGENT_GENERATED"
    confidence: float = 1.0
    scope_tags: list[str] = Field(default_factory=list)
    fingerprint: str | None = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in NODE_TYPES:
            msg = f"Invalid node type: {v}"
            raise ValueError(msg)
        return v


def _classify_state(score: float) -> str:
    for threshold, state in STATE_BOUNDARIES:
        if score < threshold:
            return state
    return STATE_BOUNDARIES[-1][1]


class FatigueState(BaseModel):
    """Current fatigue measurement."""

    score: float
    token_util: float
    scope_scatter: float = 0.0
    reread_ratio: float = 0.0
    error_density: float = 0.0
    measured_at: datetime = Field(default_factory=_now)

    @property
    def state(self) -> str:
        return _classify_state(self.score)

    @property
    def needs_checkpoint(self) -> bool:
        return self.score >= CHECKPOINT_THRESHOLD


class CheckpointData(BaseModel):
    """Serializable checkpoint snapshot.

    Supports two formats:
    - Standard: written by Python module (fatigue, summary, graph_json)
    - Rich: written by bash hook templates (goal, constraints, results)
    """

    id: str = Field(default_factory=_uuid)
    task_id: str
    created_at: datetime = Field(default_factory=_now)
    fatigue: float = 0.0
    summary: str = ""
    graph_json: dict[str, Any] = Field(default_factory=dict)
    is_emergency: bool = False
    # Rich template fields (optional)
    goal: str = ""
    active_constraints: list[str] = Field(default_factory=list)
    active_results: list[str] = Field(default_factory=list)
    current_subgoal: str = ""
    working_memory: str = ""
    task_narrative: str = ""
    recent_files: list[dict[str, Any]] = Field(default_factory=list)
    git_state: dict[str, Any] = Field(default_factory=dict)
    icpg_state: dict[str, Any] | None = None
    node_summary: dict[str, Any] = Field(default_factory=dict)


class NodeLink(BaseModel):
    """Edge between two MnemoNodes."""

    source_id: str
    target_id: str
    link_type: str = LINK_RELATED


class ConflictRecord(BaseModel):
    """Records a merge conflict resolution."""

    id: str = Field(default_factory=_uuid)
    node_a_id: str
    node_b_id: str
    conflict_type: str
    resolution: str
    resolved_at: datetime = Field(default_factory=_now)
