"""Core heartbeat scheduler — register and run periodic jobs."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

TICK_INTERVAL = 1.0  # seconds between scheduler ticks


@dataclass
class Job:
    name: str
    fn: Callable[..., Awaitable[None]]
    interval_seconds: int
    last_run: str = ""
    run_count: int = 0
    last_error: str = ""
    enabled: bool = True

    def is_due(self) -> bool:
        if not self.last_run:
            return True
        last = datetime.fromisoformat(self.last_run)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= self.interval_seconds


class HeartbeatScheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._task: asyncio.Task | None = None

    def register(
        self, name: str, fn: Callable, interval: int,
    ) -> None:
        if name in self._jobs:
            raise ValueError(f"Job '{name}' already registered")
        self._jobs[name] = Job(
            name=name, fn=fn, interval_seconds=interval,
        )

    async def tick(self) -> None:
        for job in self._jobs.values():
            if not job.enabled or not job.is_due():
                continue
            await self._run_job(job)

    async def _run_job(self, job: Job) -> None:
        try:
            await job.fn()
            job.last_error = ""
        except Exception as exc:
            job.last_error = str(exc)
            logger.warning("Job %s failed: %s", job.name, exc)
        job.last_run = datetime.now(timezone.utc).isoformat()
        job.run_count += 1

    async def trigger(self, name: str) -> dict:
        if name not in self._jobs:
            raise KeyError(name)
        job = self._jobs[name]
        await self._run_job(job)
        return {"ok": not job.last_error, "name": name}

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("Heartbeat started — %d jobs", len(self._jobs))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat stopped")

    async def _loop(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(TICK_INTERVAL)

    def status(self) -> list[dict]:
        return [
            {
                "name": j.name,
                "interval": j.interval_seconds,
                "last_run": j.last_run,
                "run_count": j.run_count,
                "last_error": j.last_error,
                "enabled": j.enabled,
            }
            for j in self._jobs.values()
        ]
