"""Agentic council PR review — run the vendored maggy.review pipeline on a GitHub PR.

The heavy pipeline (pydantic-ai + provider SDKs) is an optional extra
(`pip install maggy-harness[review]`) and is imported lazily, so the lightweight
endpoints (languages, status) work on a base install. Token resolution order:
per-request override > Maggy config (review.github_token) > env GITHUB_TOKEN.
"""

from __future__ import annotations

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
