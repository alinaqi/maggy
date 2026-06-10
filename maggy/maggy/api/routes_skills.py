"""Skills API — list, validate, create, manage skills."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


class _ValidateRequest(BaseModel):
    name: str = ""
    content: str = ""


class _CreateRequest(BaseModel):
    name: str
    description: str
    content: str
    when_to_use: str = ""
    effort: str = "medium"
    project_key: str = ""


def _get_registry(request: Request):
    reg = getattr(request.app.state, "skills", None)
    if not reg:
        raise HTTPException(503, "Skills not configured")
    return reg


@router.get("")
async def list_skills(request: Request, project_key: str = ""):
    reg = _get_registry(request)
    skills = reg.resolve(project_key or None)
    global_skills = reg.list_global()
    proj_skills = reg.list_project(project_key) if project_key else []
    return {
        "skills": [s.model_dump() for s in skills],
        "total": len(skills),
        "global_count": len(global_skills),
        "project_count": len(proj_skills),
    }


@router.get("/global")
async def list_global_skills(request: Request):
    reg = _get_registry(request)
    skills = reg.list_global()
    return {"skills": [s.model_dump() for s in skills], "total": len(skills)}


@router.get("/project/{project_key}")
async def list_project_skills(request: Request, project_key: str):
    reg = _get_registry(request)
    skills = reg.list_project(project_key)
    return {"skills": [s.model_dump() for s in skills], "total": len(skills)}


@router.post("/validate")
async def validate_skill(request: Request, body: _ValidateRequest):
    from maggy.skills.validator import SkillValidator
    v = SkillValidator()
    if body.content:
        result = v.validate_content(body.name, body.content)
    elif body.name:
        reg = _get_registry(request)
        skill = reg.get(body.name)
        if not skill:
            raise HTTPException(404, f"Skill {body.name!r} not found")
        skill_dir = Path(skill.source_path).parent
        skills_dir = skill_dir.parent
        result = v.validate_skill(skill_dir, skills_dir)
    else:
        raise HTTPException(400, "Provide name or content")
    return result.model_dump()


@router.post("/validate-all")
async def validate_all(request: Request, project_key: str = ""):
    from maggy.skills.validator import SkillValidator
    reg = _get_registry(request)
    v = SkillValidator()
    skills_dir = reg._global_dir
    results = v.validate_all(skills_dir)
    return {
        "results": [r.model_dump() for r in results],
        "total": len(results),
        "valid": sum(1 for r in results if r.is_valid),
        "invalid": sum(1 for r in results if not r.is_valid),
    }


@router.post("", status_code=201)
async def create_skill(request: Request, body: _CreateRequest):
    from maggy.skills.validator import SkillValidator
    reg = _get_registry(request)
    fm = (
        f"---\nname: {body.name}\n"
        f"description: {body.description}\n"
        f"when-to-use: {body.when_to_use}\n"
        f"effort: {body.effort}\n---\n\n"
    )
    full_content = fm + body.content
    v = SkillValidator()
    result = v.validate_content(body.name, full_content)
    if not result.is_valid:
        raise HTTPException(422, {
            "message": "Validation failed",
            "findings": result.findings,
        })
    if body.project_key:
        proj_path = reg._project_paths.get(body.project_key)
        if not proj_path:
            raise HTTPException(404, f"Project {body.project_key!r} not found")
        target = Path(proj_path) / ".claude" / "skills" / body.name
    else:
        target = reg._global_dir / body.name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(full_content)
    reg.reload(body.project_key or None)
    return {"name": body.name, "status": "created", "path": str(target)}


@router.post("/reload")
async def reload_skills(request: Request, project_key: str = ""):
    reg = _get_registry(request)
    count = reg.reload(project_key or None)
    return {"count": count, "status": "reloaded"}


@router.get("/{name}")
async def get_skill(request: Request, name: str, project_key: str = ""):
    reg = _get_registry(request)
    skill = reg.get(name, project_key or None)
    if not skill:
        raise HTTPException(404, f"Skill {name!r} not found")
    return skill.model_dump()
