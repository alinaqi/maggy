"""Orchestrator API — spawn parallel teams, track progress."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


class SpawnRequest(BaseModel):
    task_id: str
    parallel: bool = True


class TeamSummary(BaseModel):
    team_id: str
    task_id: str
    status: str
    subtask_count: int


@router.post("/spawn", status_code=201)
async def spawn_team(req: SpawnRequest, request: Request):
    """Decompose a task and spawn a parallel container team."""
    orch = request.app.state.orchestrator
    provider = request.app.state.provider
    task = await provider.get_task(req.task_id)
    if not task:
        raise HTTPException(404, f"Task {req.task_id} not found")
    desc = getattr(task, "description", "") or ""
    subtasks = await orch.decompose(task.title, desc)
    session = await orch.spawn_team(req.task_id, subtasks)
    return _summarize(session)


@router.get("/teams")
def list_teams(request: Request):
    """List all active teams."""
    orch = request.app.state.orchestrator
    return [_summarize(t) for t in orch.list_teams()]


@router.get("/teams/{team_id}")
def get_team(team_id: str, request: Request):
    """Get team status and subtask progress."""
    session = request.app.state.orchestrator.get_team(team_id)
    if not session:
        raise HTTPException(404, f"Team {team_id} not found")
    return _summarize(session)


@router.post("/teams/{team_id}/cancel")
async def cancel_team(team_id: str, request: Request):
    """Cancel a running team."""
    await request.app.state.orchestrator.cancel_team(team_id)
    return {"status": "cancelled", "team_id": team_id}


def _summarize(session) -> dict:
    """Convert TeamSession to API response dict."""
    return {
        "team_id": session.team_id,
        "task_id": session.task_id,
        "status": session.status,
        "subtask_count": len(session.subtasks),
    }
