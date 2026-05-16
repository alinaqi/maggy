"""Plugin API — list, enable, disable, trigger plugins."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from maggy.plugins.manager import get_plugin_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("")
async def list_plugins(request: Request):
    """List loaded plugins and their hooks."""
    pm = get_plugin_manager()
    plugins = []
    for pid, manifest in pm.plugins.items():
        plugins.append({
            "id": manifest.id,
            "version": manifest.version,
            "permissions": manifest.permissions,
            "hooks": [h["event"] for h in manifest.hooks],
        })
    return {"plugins": plugins, "total": len(plugins)}


@router.post("/reload")
async def reload_plugins(request: Request):
    """Reload all plugins from disk."""
    pm = get_plugin_manager()
    loaded = pm.load_all()
    return {"loaded": loaded}


@router.post("/emit/{event_name}")
async def emit_event(request: Request, event_name: str, payload: dict | None = None):
    """Manually emit an event to test plugins."""
    pm = get_plugin_manager()
    await pm.emit(event_name, payload or {})
    return {"event": event_name, "status": "emitted"}
