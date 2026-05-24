"""Executor backend — wraps executor_stream for high-blast tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from maggy.services.chat_models import ChatSession
    from maggy.services.executor import ExecutorService

logger = logging.getLogger(__name__)

_PASSTHROUGH_TYPES = frozenset({"search", "docs", "review"})
_BLAST_THRESHOLD = 4


class ExecutorBackend:
    name = "executor"

    def __init__(self, executor: ExecutorService) -> None:
        self._executor = executor

    def handles(self, model: str) -> bool:
        return False

    def handles_decision(
        self, model: str, blast: int, task_type: str,
    ) -> bool:
        if task_type in _PASSTHROUGH_TYPES:
            return False
        return blast >= _BLAST_THRESHOLD

    async def execute(
        self,
        model: str,
        message: str,
        session: ChatSession,
        working_dir: str,
        project_key: str,
    ) -> AsyncGenerator[dict, None]:
        from maggy.services.chat_executor_bridge import (
            executor_stream,
        )
        decision = _FakeDecision(model, task_type="general")
        async for chunk in executor_stream(
            self._executor, decision, message, working_dir,
        ):
            yield chunk


class _FakeDecision:
    def __init__(self, model: str, task_type: str = "general"):
        self.model = model
        self.task_type = task_type
        self.blast = _BLAST_THRESHOLD
