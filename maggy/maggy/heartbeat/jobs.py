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


async def collect_signals(app) -> None:
    """Record periodic observability signals."""
    obs = getattr(app.state, "observability", None)
    cfg = getattr(app.state, "cfg", None)
    if not obs or not cfg:
        return
    try:
        for cb in cfg.codebases:
            obs.record_signal(cb.key, "heartbeat", 1.0)
    except Exception as exc:
        logger.warning("collect_signals failed: %s", exc)
        raise


async def learn_from_prs(app) -> None:
    """Fetch PR comments and extract learning signals."""
    engram = getattr(app.state, "engram", None)
    cfg = getattr(app.state, "cfg", None)
    if not engram or not cfg:
        return
    try:
        from maggy.learn.pr_learner import fetch_pr_comments, extract_pr_signals
        from maggy.learn._writer import write_signal
        for cb in cfg.codebases:
            repo_path = getattr(cb, "repo_dir", "") or getattr(cb, "path", "")
            if not repo_path:
                continue
            comments = await fetch_pr_comments(repo_path, limit=5)
            signals = extract_pr_signals(comments)
            pkey = getattr(cb, "key", "")
            for sig in signals:
                await write_signal(engram, "pr-feedback", sig, pkey)
    except Exception as exc:
        logger.warning("learn_from_prs failed: %s", exc)


async def rescan_repos(app) -> None:
    """Discover new git repos and auto-register them."""
    registry = getattr(app.state, "registry", None)
    if not registry:
        return
    try:
        from maggy.discovery import discover_repos
        from maggy.config import ProjectConfig
        existing = {p.name for p in registry.list()}
        repos = discover_repos()
        added = 0
        for repo in repos:
            name = repo["key"]
            if name in existing:
                continue
            project = ProjectConfig(
                name=name, repo=f"local/{name}",
                path=repo["path"], default_branch="main",
            )
            try:
                registry.add(project)
                added += 1
            except ValueError:
                pass
        if added:
            logger.info("rescan_repos: registered %d new repos", added)
    except Exception as exc:
        logger.warning("rescan_repos failed: %s", exc)


async def consolidate_learnings(app) -> None:
    """Run memory hygiene on learning namespaces."""
    engram = getattr(app.state, "engram", None)
    if not engram:
        return
    try:
        from maggy.learn.consolidator import consolidate_all
        results = consolidate_all(engram)
        total = sum(s.get("expired", 0) + s.get("evicted", 0) for s in results.values())
        if total:
            logger.info("Learning consolidation: cleaned %d records", total)
    except Exception as exc:
        logger.warning("consolidate_learnings failed: %s", exc)
