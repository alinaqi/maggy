"""Restrict request-supplied project_dir to registered project paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Query, Request


def registered_roots(cfg: Any) -> list[Path]:
    """Realpaths of every configured project and codebase path."""
    raw = [p.path for p in cfg.projects] + [c.path for c in cfg.codebases]
    return [_real(p) for p in raw if p and p.strip()]


def _real(path: str) -> Path:
    return Path(os.path.realpath(os.path.expanduser(path)))


def resolve_project_dir(cfg: Any, project_dir: str) -> str:
    """Return the realpath of project_dir, or raise 400/403."""
    if not project_dir or not project_dir.strip():
        raise HTTPException(status_code=400, detail="project_dir is required")
    roots = registered_roots(cfg) if cfg is not None else []
    target = _real(project_dir)
    if not any(target.is_relative_to(root) for root in roots):
        raise HTTPException(
            status_code=403,
            detail="project_dir is not inside a registered project",
        )
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="project_dir not found")
    return str(target)


def guarded_project_dir(
    request: Request, project_dir: str = Query(""),
) -> str:
    """FastAPI dependency: a sandboxed, resolved project_dir."""
    cfg = getattr(request.app.state, "cfg", None)
    return resolve_project_dir(cfg, project_dir)
