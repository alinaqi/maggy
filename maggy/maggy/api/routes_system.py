"""System status endpoints — global tool detection, no project required."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from maggy.api.auth import check_auth

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Global system status: AI CLIs, dev tools, stack."""
    check_auth(request, x_api_key)
    from maggy.services.project_bootstrap import (
        detect_cli_inventory,
        detect_dev_tools,
    )
    clis = detect_cli_inventory()
    tools = detect_dev_tools()
    return {
        "clis": [_cli(c) for c in clis],
        "tools": [_cli(c) for c in tools],
    }


def _cli(c) -> dict:
    return {
        "name": c.name, "installed": c.installed,
        "path": c.path, "category": c.category,
    }
