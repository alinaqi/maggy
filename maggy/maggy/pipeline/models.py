"""Pipeline data models — context and result."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineContext:
    """Input context for a pipeline run."""

    session_id: str
    message: str
    project_key: str
    working_dir: str
    blast_override: int | None = None
    task_type_override: str | None = None
    allowed_models: list[str] | None = None


@dataclass
class PipelineResult:
    """Outcome of a pipeline run."""

    model: str
    backend: str
    blast: int
    task_type: str
    reason: str
    latency_ms: float
    cost_usd: float
    tokens_in: int
    tokens_out: int
    success: bool
    error: str = ""
    fallback_used: str = ""
