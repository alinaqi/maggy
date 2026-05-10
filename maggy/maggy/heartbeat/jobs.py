"""Built-in heartbeat jobs — wire to existing services."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from maggy.engram.record import Validity

logger = logging.getLogger(__name__)


async def refresh_history(app) -> None:
    """Re-parse CLI session data."""
    history = getattr(app.state, "history", None)
    if not history:
        return
    try:
        history.analyze()
    except Exception as exc:
        logger.warning("refresh_history failed: %s", exc)
        raise


async def expire_engrams(app) -> None:
    """Mark expired engrams."""
    engram = getattr(app.state, "engram", None)
    if not engram:
        return
    try:
        records = engram.query(active_only=True, limit=500)
        now = datetime.now(timezone.utc)
        for rec in records:
            if _is_expired(rec, now):
                rec.validity = Validity.expired
                engram.write(rec)
    except Exception as exc:
        logger.warning("expire_engrams failed: %s", exc)
        raise


def _is_expired(rec, now) -> bool:
    """Check if an engram's TTL has elapsed."""
    tags = getattr(rec, "tags", []) or []
    ttl_tag = next((t for t in tags if t.startswith("ttl:")), None)
    if not ttl_tag:
        return False
    try:
        ttl = int(ttl_tag.split(":")[1])
    except (IndexError, ValueError):
        return False
    created = rec.created_at
    if not created:
        return False
    from datetime import timedelta
    created_dt = datetime.fromisoformat(created)
    return (now - created_dt).total_seconds() > ttl * 3600


async def self_improve(app) -> None:
    """Run self-improvement analysis."""
    introspector = getattr(app.state, "introspector", None)
    if not introspector:
        return
    try:
        introspector.analyze()
    except Exception as exc:
        logger.warning("self_improve failed: %s", exc)
        raise


async def mesh_heartbeat(app) -> None:
    """Discover peers, announce self, publish shares."""
    mesh = getattr(app.state, "mesh", None)
    if not mesh:
        return
    cfg = getattr(app.state, "cfg", None)
    if not cfg:
        return
    try:
        token = cfg.issue_tracker.github.token
        if token and cfg.mesh.git_discovery:
            await mesh.discover(token)
            await mesh.announce_all(token)
    except Exception as exc:
        logger.warning("mesh_heartbeat failed: %s", exc)
        raise
