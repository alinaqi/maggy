"""Planning REST endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from .auth import check_auth

router = APIRouter(prefix="/api/planning", tags=["planning"])


class PlanGenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    blast_score: int = Field(default=0, ge=0, le=10)
    files: list[str] | None = None


@router.post("/generate")
async def generate_plan(
    request: Request,
    body: PlanGenerateRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Generate a plan for a task."""
    check_auth(request, x_api_key)
    svc = request.app.state.planning
    if not svc:
        return {"error": "planning not configured"}
    from maggy.planning import PlanRequest
    req = PlanRequest(
        task=body.task,
        blast_score=body.blast_score,
        file_context=body.files,
    )
    result = svc.plan_task(req)
    plan = result["plan"]
    response = {
        "mode": result["mode"],
        "plan": asdict(plan),
    }
    if result.get("diff"):
        response["diff"] = asdict(result["diff"])
    return response
