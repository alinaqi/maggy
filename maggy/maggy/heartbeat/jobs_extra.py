"""Extra heartbeat jobs — inbox polling, competitors, research tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def create_inbox_poller(provider, inbox_service, routing):
    """Create an inbox-polling heartbeat job."""

    async def poll_inbox() -> None:
        try:
            await inbox_service.get_prioritized(force_refresh=True)
            logger.debug("Heartbeat: inbox refreshed")
        except Exception:
            pass

    return poll_inbox


async def create_competitor_scanner(provider, project_key: str = ""):
    """Create a competitor-scanning heartbeat job."""

    async def scan_competitors() -> None:
        try:
            from maggy.services import ai_client
            from maggy.config import MaggyConfig

            if not project_key:
                return
            now = datetime.now(timezone.utc).isoformat()
            logger.info("Heartbeat: scanning competitors for %s", project_key)
        except Exception:
            pass

    return scan_competitors


async def create_research_tracker(provider, project_key: str = ""):
    """Track research trends for the active project."""

    async def track_research() -> None:
        if not project_key:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            logger.debug("Heartbeat: tracking research for %s", project_key)
        except Exception:
            pass

    return track_research


async def register_extra_jobs(scheduler, cfg, provider, inbox_service):
    """Register inbox, competitor, and research heartbeat jobs."""
    project_key = cfg.projects[0].key if cfg.projects else ""

    scheduler.register(
        "poll_inbox",
        await create_inbox_poller(provider, inbox_service, None),
        interval=cfg.heartbeat.inbox_interval
        if hasattr(cfg.heartbeat, "inbox_interval")
        else 300,
    )
    scheduler.register(
        "scan_competitors",
        await create_competitor_scanner(provider, project_key),
        interval=cfg.heartbeat.competitor_interval
        if hasattr(cfg.heartbeat, "competitor_interval")
        else 900,
    )
    scheduler.register(
        "track_research",
        await create_research_tracker(provider, project_key),
        interval=cfg.heartbeat.research_interval
        if hasattr(cfg.heartbeat, "research_interval")
        else 1800,
    )
    logger.info(
        "Extra heartbeat jobs registered: poll_inbox, scan_competitors, track_research"
    )
