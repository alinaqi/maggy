"""Setup and onboarding routes — detect missing config, guide users."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from maggy import config as config_mod

router = APIRouter(prefix="/api/setup", tags=["setup"])


class ConfigureRequest(BaseModel):
    org_name: str = ""
    github_org: str = ""
    github_repos: list[str] = Field(default_factory=list)
    competitor_categories: list[str] = Field(
        default_factory=list,
    )


def _step(label: str, ok: bool, hint: str = "") -> dict:
    """Build a single setup step status."""
    return {
        "label": label,
        "status": "done" if ok else "missing",
        "hint": hint,
    }


def _build_steps(cfg) -> list[dict]:
    """Detect what's configured and what's missing."""
    gh = cfg.issue_tracker.github
    return [
        _step("GitHub token", bool(gh.token), ""),
        _step("GitHub organization", bool(gh.org), ""),
        _step(
            "GitHub repositories", bool(gh.repos),
            "Select repos to track issues from",
        ),
        _step(
            "AI provider",
            bool(cfg.ai.api_key) or _has_claude_cli(),
            "",
        ),
        _step("Codebases", bool(cfg.codebases), ""),
    ]


def _has_claude_cli() -> bool:
    """Check if claude CLI is available."""
    import shutil
    return shutil.which("claude") is not None


def _discover_summary() -> dict:
    """Run discovery and return summary."""
    from maggy.discovery import (
        discover_cli_auth,
        discover_clis,
        discover_env_tokens,
    )
    return {
        "clis": discover_clis(),
        "cli_auth": discover_cli_auth(),
        "tokens": discover_env_tokens(),
    }


@router.get("/status")
async def setup_status(request: Request) -> dict:
    """What's configured, what's missing."""
    cfg = request.app.state.cfg
    steps = _build_steps(cfg)
    done = sum(1 for s in steps if s["status"] == "done")
    discovery = _discover_summary()
    return {
        "configured": request.app.state.mode == "full",
        "mode": request.app.state.mode,
        "steps": steps,
        "progress": f"{done}/{len(steps)}",
        "codebases": len(cfg.codebases),
        "github_org": cfg.issue_tracker.github.org,
        "discovery": discovery,
    }


@router.post("/configure")
async def configure(
    request: Request, body: ConfigureRequest,
) -> dict:
    """Update config sections dynamically."""
    cfg = request.app.state.cfg
    if body.org_name:
        cfg.org.name = body.org_name
    if body.github_org:
        cfg.issue_tracker.github.org = body.github_org
    if body.github_repos:
        cfg.issue_tracker.github.repos = body.github_repos
    if body.competitor_categories:
        cfg.competitors.categories = body.competitor_categories
    config_mod.save(cfg)
    return {"saved": True}


@router.post("/reload")
async def reload_config(request: Request) -> dict:
    """Reload config and reinitialize services."""
    from maggy.main import reconfigure
    reconfigure(request.app)
    mode = request.app.state.mode
    return {"mode": mode, "reloaded": True}


@router.get("/discover-repos")
async def discover_repos(request: Request) -> dict:
    """Return repos found on disk, grouped by org."""
    from maggy.discovery import full_discovery
    result = full_discovery()
    return {
        "github_org": result.github_org,
        "github_orgs": result.github_orgs,
        "repos": [
            {"key": r["key"], "path": r["path"]}
            for r in result.repos
        ],
        "cli_auth": result.cli_auth,
        "clis": result.clis,
    }


@router.post("/auto-configure")
async def auto_configure(request: Request) -> dict:
    """Run auto-discovery, save config, reload."""
    cfg = config_mod.auto_configure()
    request.app.state.cfg = cfg
    from maggy.main import reconfigure
    reconfigure(request.app)
    return {
        "mode": request.app.state.mode,
        "codebases": len(cfg.codebases),
        "github_org": cfg.issue_tracker.github.org,
        "github_repos": cfg.issue_tracker.github.repos,
        "has_token": bool(cfg.issue_tracker.github.token),
    }


@router.get("/cli-models")
async def cli_models() -> dict:
    """Auto-discover AI CLIs and their capabilities."""
    from maggy.adapters.cli_discovery import discover_all
    result = discover_all()
    profiles = []
    for name, p in result.profiles.items():
        profiles.append({
            "name": name, "installed": p.installed,
            "version": p.version,
            "prompt_flag": p.prompt_flag,
            "work_dir_flag": p.work_dir_flag,
            "auto_approve": p.auto_approve_flag,
            "afk": p.afk_flag,
        })
    installed = [p["name"] for p in profiles if p["installed"]]
    return {
        "profiles": profiles,
        "installed": installed,
        "ready": len(installed) > 0,
    }
