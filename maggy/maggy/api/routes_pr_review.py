"""Agentic council PR review — run the vendored maggy.review pipeline on a GitHub PR.

The heavy pipeline (pydantic-ai + provider SDKs) is an optional extra
(`pip install maggy-harness[review]`) and is imported lazily, so the lightweight
endpoints (languages, status) work on a base install. Token resolution order:
per-request override > Maggy config (review.github_token) > env GITHUB_TOKEN.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from maggy.api.auth import check_auth
from maggy.review import config as review_config
from maggy.review import languages as review_languages

router = APIRouter(prefix="/api/pr-review", tags=["pr-review"])


class RunRequest(BaseModel):
    owner: str
    repo: str
    pr_number: int
    dry_run: bool | None = None       # None -> fall back to config.review.default_dry_run
    github_token: str | None = None   # per-request override (beats config + env)
    repo_path: str | None = None      # local checkout for the static gate / FP filter


class ReviewConfigUpdate(BaseModel):
    github_token: str | None = None   # set the bot token; None/"" = leave unchanged
    clear_token: bool = False         # explicitly clear it (fall back to env GITHUB_TOKEN)
    default_dry_run: bool | None = None


def _mask(tok: str) -> str:
    """Never return a raw token — only a recognizable last-4 hint."""
    return f"…{tok[-4:]}" if tok and len(tok) >= 4 else ("set" if tok else "")


def _config_view(rc) -> dict:
    """Masked, safe-to-return view of the reviewer config."""
    return {
        "token_set": bool(rc.github_token),
        "token_hint": _mask(rc.github_token),
        "uses_env_fallback": (not rc.github_token) and bool(os.environ.get("GITHUB_TOKEN")),
        "default_dry_run": rc.default_dry_run,
    }


def _register_config_languages(cfg) -> None:
    """Register any user-defined languages from config into the skill registry."""
    review_languages.load_from_config(getattr(cfg.review, "languages", []))


def _resolve_token(cfg, override: str | None) -> str | None:
    """Per-request override > Maggy config > env GITHUB_TOKEN."""
    return review_config.resolve_token(override, getattr(cfg.review, "github_token", ""))


@router.get("/languages")
async def list_languages(request: Request, x_api_key: str | None = Header(None)) -> dict:
    """All languages the reviewer can skill up on (built-ins + config-defined)."""
    check_auth(request, x_api_key)
    _register_config_languages(request.app.state.cfg)
    return {"languages": review_languages.supported()}


@router.get("/status")
async def status(request: Request, x_api_key: str | None = Header(None)) -> dict:
    """Is the review extra installed? Which model seats + token are available?"""
    check_auth(request, x_api_key)
    cfg = request.app.state.cfg
    try:
        import pydantic_ai  # noqa: F401
        installed = True
    except ImportError:
        installed = False
    models = [name for name, _f, _l, _t in review_config.available()] if installed else []
    return {
        "installed": installed,
        "hint": "" if installed else "Install the reviewer: pip install maggy-harness[review]",
        "models": models,
        "token_configured": bool(_resolve_token(cfg, None)),
        "languages": review_languages.supported(),
    }


@router.get("/config")
async def get_config(request: Request, x_api_key: str | None = Header(None)) -> dict:
    """Reviewer-bot config (masked). The raw token is never returned."""
    check_auth(request, x_api_key)
    return _config_view(request.app.state.cfg.review)


@router.post("/config")
async def set_config(
    request: Request, body: ReviewConfigUpdate, x_api_key: str | None = Header(None),
) -> dict:
    """Save the reviewer-bot token / dry-run default to Maggy config."""
    check_auth(request, x_api_key)
    cfg = request.app.state.cfg
    rc = cfg.review
    if body.clear_token:
        rc.github_token = ""
    elif body.github_token is not None and body.github_token.strip():
        rc.github_token = body.github_token.strip()
    if body.default_dry_run is not None:
        rc.default_dry_run = body.default_dry_run
    from maggy import config as config_mod
    config_mod.save(cfg)
    return _config_view(rc)


def _serialize(out: dict) -> dict:
    """JSON-safe view of run_review's result: verdict + findings + cost + meta."""
    final = out["final"]
    plan = out["plan"]
    return {
        "decision": final.decision,
        "summary": final.summary,
        "findings": [f.model_dump() for f in final.findings],
        "blast_radius": plan.blast_radius.size,
        "council": len(out.get("chunks", []) or []),
        "post": out.get("post"),
        "cost": out.get("cost"),
    }


@router.post("/run")
async def run(request: Request, body: RunRequest, x_api_key: str | None = Header(None)) -> dict:
    """Run the council on a PR. dry_run (default from config) skips the GitHub write."""
    check_auth(request, x_api_key)
    cfg = request.app.state.cfg
    token = _resolve_token(cfg, body.github_token)
    if not token:
        raise HTTPException(400, "No GitHub token — set review.github_token, pass github_token, or export GITHUB_TOKEN")
    try:
        from maggy.review.pipeline import run_review
    except ImportError:
        raise HTTPException(503, "Reviewer not installed — run: pip install maggy-harness[review]")

    _register_config_languages(cfg)
    dry = cfg.review.default_dry_run if body.dry_run is None else body.dry_run
    repo_path = body.repo_path or cfg.review.repo_paths.get(f"{body.owner}/{body.repo}")
    logs: list[str] = []
    try:
        out = await run_review(
            body.owner, body.repo, body.pr_number,
            dry_run=dry, repo_path=repo_path, on_log=logs.append, token=token,
        )
    except SystemExit as exc:        # pipeline raises SystemExit for config problems
        raise HTTPException(400, str(exc))
    except Exception as exc:          # noqa: BLE001 — surface the failure, don't 500 opaquely
        raise HTTPException(502, f"Review failed: {type(exc).__name__}: {exc}")
    return {"dry_run": dry, **_serialize(out), "logs": logs[-40:]}
