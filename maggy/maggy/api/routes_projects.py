"""Project registry REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(prefix="/api/projects", tags=["projects"])


class _ProjectIn(BaseModel):
    name: str
    repo: str
    path: str
    default_branch: str = "main"


@router.get("")
async def list_projects(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """List all registered projects."""
    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        return []
    return [
        {"name": p.name, "repo": p.repo, "path": p.path}
        for p in registry.list()
    ]


@router.get("/{name}")
async def get_project(
    name: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get a single project by name."""
    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(404, "Not configured")
    project = registry.get(name)
    if not project:
        raise HTTPException(404, f"{name!r} not found")
    return {
        "name": project.name,
        "repo": project.repo,
        "path": project.path,
    }


@router.post("", status_code=201)
async def add_project(
    body: _ProjectIn,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Register a new project."""
    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    from maggy.config import ProjectConfig
    project = ProjectConfig(
        name=body.name, repo=body.repo,
        path=body.path, default_branch=body.default_branch,
    )
    try:
        registry.add(project)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"name": project.name, "status": "created"}


@router.delete("/{name}")
async def remove_project(
    name: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Remove a project by name."""
    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    if not registry.remove(name):
        raise HTTPException(404, f"{name!r} not found")
    return {"name": name, "status": "removed"}
