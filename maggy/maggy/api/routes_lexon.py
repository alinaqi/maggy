"""Lexon REST endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from .auth import check_auth

router = APIRouter(prefix="/api/lexon", tags=["lexon"])


class LearnRequest(BaseModel):
    phrase: str = Field(..., min_length=1, max_length=500)
    tool: str = Field(..., min_length=1, max_length=100)


@router.get("/parse")
async def parse_intent(
    request: Request,
    q: str = "",
    x_api_key: str | None = Header(None),
) -> dict:
    """Parse a phrase into a tool intent."""
    check_auth(request, x_api_key)
    lexon = request.app.state.lexon
    if not lexon:
        return {"error": "lexon not configured"}
    record = lexon.route(q)
    return asdict(record)


@router.post("/learn")
async def learn_mapping(
    request: Request,
    body: LearnRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Record a confirmed phrase-to-tool mapping."""
    check_auth(request, x_api_key)
    lexon = request.app.state.lexon
    if not lexon:
        return {"error": "lexon not configured"}
    lexon.learn(body.phrase, body.tool)
    return {"status": "learned"}
