"""Async write isolation + content-hash dedup for learning signals."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _content_hash(namespace: str, content: str, project_key: str) -> str:
    raw = f"{namespace}:{project_key}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def write_signal(
    engram_store,
    namespace: str,
    signal: dict,
    project_key: str = "",
) -> bool:
    if engram_store is None:
        return False
    from maggy.engram.record import EngramRecord
    try:
        content = signal["content"]
        dedup_id = _content_hash(namespace, content, project_key)
        existing = await asyncio.to_thread(engram_store.get, dedup_id)
        if existing and existing.is_active:
            return False
        tags = list(signal.get("tags", []))
        if project_key:
            tags.append(f"project:{project_key}")
        record = EngramRecord(
            engram_id=dedup_id,
            namespace=namespace,
            memory_type=signal.get("memory_type", "fact"),
            content=content,
            origin="inferred",
            confidence=signal.get("confidence", 0.7),
            tags=tags,
        )
        await asyncio.to_thread(engram_store.write, record)
        return True
    except Exception as exc:
        logger.debug("Learning write failed: %s", exc)
        return False


def fire_and_forget_write(
    engram_store,
    namespace: str,
    signals: list[dict],
    project_key: str = "",
) -> None:
    if engram_store is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _batch():
        for sig in signals:
            await write_signal(engram_store, namespace, sig, project_key)

    loop.create_task(_batch())
