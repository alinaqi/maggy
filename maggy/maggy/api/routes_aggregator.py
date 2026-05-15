"""Multi-source task aggregator — _project_specs + GitHub + Asana."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aggregator", tags=["aggregator"])


@router.get("/tasks")
async def list_all_tasks(request: Request, project: str = ""):
    """List pending tasks from all sources for a given project."""
    tasks: list[dict] = []
    cfg = request.app.state.cfg

    # Source 1: _project_specs
    if project:
        for cb in cfg.codebases:
            if cb.key == project and cb.path:
                from maggy.services.progress_engine import read_project_specs
                specs = read_project_specs(cb.path)
                for t in specs.get("tasks", []):
                    t["source"] = "_project_specs"
                tasks.extend(specs.get("tasks", []))
                break

    # Source 2: GitHub / Asana via inbox
    try:
        inbox_svc = getattr(request.app.state, "inbox", None)
        if inbox_svc:
            inbox_tasks = await inbox_svc.get_prioritized(force_refresh=False)
            for it in inbox_tasks:
                if not project or it.get("project", "").startswith(project):
                    tasks.append({
                        "id": it.get("id", ""),
                        "title": it.get("title", ""),
                        "status": it.get("status", "open"),
                        "source": it.get("provider", "github"),
                        "url": it.get("url", ""),
                        "priority": it.get("priority", 0),
                    })
    except Exception as e:
        logger.debug("Inbox tasks unavailable: %s", e)

    # Deduplicate by title
    seen = set()
    unique = []
    for t in tasks:
        key = t["title"].lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(t)

    unique.sort(key=lambda t: t.get("priority", 0), reverse=True)
    return {"tasks": unique, "total": len(unique)}


@router.post("/execute-all")
async def execute_all_tasks(request: Request, project: str = ""):
    """Auto-execute all pending tasks with TDD for the given project."""
    from maggy.services.progress_engine import ProgressEngine, read_project_specs

    pe = ProgressEngine(project_key=project)
    results: list[dict] = []

    # Collect tasks from _project_specs
    if project:
        for cb in request.app.state.cfg.codebases:
            if cb.key == project and cb.path:
                specs = read_project_specs(cb.path)
                for t in specs.get("tasks", []):
                    if t["status"] == "pending":
                        pe.record_step(
                            "claude", "ANALYZE", "queued",
                            detail=t["title"],
                        )
                        results.append(t)

    return {
        "queued": len(results),
        "tasks": results,
        "message": f"Queued {len(results)} tasks for execution. "
                   f"Use /api/execute for individual task execution.",
    }
