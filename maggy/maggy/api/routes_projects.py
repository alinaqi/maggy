"""Project registry REST endpoints."""

from __future__ import annotations

import json
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(prefix="/api/projects", tags=["projects"])


class _ProjectIn(BaseModel):
    name: str
    repo: str
    path: str
    default_branch: str = "main"


class _NewProjectIn(BaseModel):
    name: str
    directory: str = ""


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

@router.post("/create-new")
async def create_new_project(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    import json as _json
    raw = await request.json()
    body = _NewProjectIn(name=raw.get("name",""), directory=raw.get("directory",""))
    """Create a new project directory and register it."""
    import subprocess
    from pathlib import Path

    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")

    dir_name = body.directory or body.name.lower().replace(" ", "-")
    project_path = Path.home() / "Documents" / dir_name

    try:
        project_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(500, f"Cannot create directory: {e}") from e

    # Register the project
    from maggy.config import ProjectConfig
    project = ProjectConfig(
        name=body.name, repo=f"local/{dir_name}",
        path=str(project_path), default_branch="main",
    )
    try:
        registry.add(project)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {
        "ok": True,
        "name": body.name,
        "path": str(project_path),
        "message": f"Created {dir_name}/ — open terminal and run: cd {project_path} && claude"
    }
@router.get("/{name}/tasks")
async def list_tasks(
    name: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get tasks for a project using its configured tracker."""
    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    project = registry.get(name)
    if not project:
        raise HTTPException(404, f"Project '{name}' not found")

    from maggy.services.task_provider import get_provider, Task
    provider = get_provider(getattr(project, "tracker", "native") or "native")
    config = {"tracker_type": getattr(project, "tracker", "native") or "native"}

    tasks = await provider.list_tasks(getattr(project, "path", ""), config)
    return {"tasks": [t.__dict__ for t in tasks], "tracker": config["tracker_type"]}


@router.post("/{name}/tasks")
async def create_task(
    name: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Create a task in the project's tracker."""
    import json as _json
    body = await request.json()
    title = body.get("title", "")
    if not title:
        raise HTTPException(400, "title required")

    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    project = registry.get(name)
    if not project:
        raise HTTPException(404, f"Project '{name}' not found")

    from maggy.services.task_provider import get_provider
    provider = get_provider(getattr(project, "tracker", "native") or "native")
    config = {"tracker_type": getattr(project, "tracker", "native") or "native"}

    task = await provider.create_task(getattr(project, "path", ""), config, title)
    return {"task": task.__dict__}


@router.patch("/{name}/tasks/{task_id}")
async def update_task(
    name: str,
    task_id: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Update task status."""
    import json as _json
    body = await request.json()
    status = body.get("status", "done")

    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    project = registry.get(name)
    if not project:
        raise HTTPException(404, f"Project '{name}' not found")

    from maggy.services.task_provider import get_provider
    provider = get_provider(getattr(project, "tracker", "native") or "native")
    config = {"tracker_type": getattr(project, "tracker", "native") or "native"}

    task = await provider.update_task(getattr(project, "path", ""), config, task_id, status)
    return {"task": task.__dict__}

@router.patch("/{name}/config")
async def update_project_config(
    name: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Update per-project config (tracker, enabled plugins)."""
    import json as _json
    body = await request.json()

    check_auth(request, x_api_key)
    registry = request.app.state.registry
    if not registry:
        raise HTTPException(503, "Not configured")
    project = registry.get(name)
    if not project:
        raise HTTPException(404, f"Project '{name}' not found")

    if "tracker" in body:
        project.tracker = body["tracker"]
    if "enabled_plugins" in body:
        project.enabled_plugins = body["enabled_plugins"]

    # Persist config update
    registry._save() if hasattr(registry, "_save") else None

    return {"ok": True, "tracker": getattr(project, "tracker", "native") or "native"}


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
