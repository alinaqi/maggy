"""Pipeline orchestrator — single entry point for all chat backends."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, AsyncGenerator

from maggy.pipeline.models import PipelineContext, PipelineResult

if TYPE_CHECKING:
    from maggy.services.chat_models import ChatSession

logger = logging.getLogger(__name__)


class ChatPipeline:
    def __init__(
        self, routing, budget,
        backends: list, log_store,
        blueprints=None, reviewer_scores=None,
        engram=None,
    ) -> None:
        self._routing = routing
        self._budget = budget
        self._backends = list(backends)
        self._log_store = log_store
        self._blueprints = blueprints
        self._reviewer_scores = reviewer_scores
        self._engram = engram

    def add_backend(self, backend) -> None:
        self._backends.append(backend)

    def _select_backend(self, model: str):
        for b in self._backends:
            if b.handles(model):
                return b
        return self._backends[0] if self._backends else None

    async def run(
        self,
        ctx: PipelineContext,
        session: ChatSession,
        model: str,
        blast: int,
        task_type: str,
        reason: str,
    ) -> AsyncGenerator[dict, None]:
        t0 = time.monotonic()
        backend = self._select_backend(model)
        cost = 0.0
        tokens_in = 0
        tokens_out = 0
        error = ""
        fallback_used = ""
        content_parts: list[str] = []
        tool_events: list[str] = []
        has_error = False

        async for chunk in backend.execute(
            model, ctx.message, session,
            ctx.working_dir, ctx.project_key,
        ):
            ct = chunk.get("type", "")
            if ct == "error":
                has_error = True
                error = chunk.get("content", "")
            if ct == "result":
                cost = chunk.get("cost_usd", 0.0)
                tokens_in = chunk.get("input_tokens", 0)
                tokens_out = chunk.get("output_tokens", 0)
            if ct in ("text", "result"):
                content_parts.append(chunk.get("content", ""))
            if ct == "tool_use":
                tool_events.append(chunk.get("tool", "unknown"))
            yield chunk

        if has_error and backend.name != "claude":
            fb = self._find_fallback()
            if fb:
                fallback_used = fb.name
                has_error = False
                error = ""
                content_parts.clear()
                tool_events.clear()
                yield {
                    "type": "agent_status",
                    "content": f"Falling back to {fb.name}",
                }
                async for chunk in fb.execute(
                    model, ctx.message, session,
                    ctx.working_dir, ctx.project_key,
                ):
                    ct = chunk.get("type", "")
                    if ct == "error":
                        has_error = True
                        error = chunk.get("content", "")
                    if ct == "result":
                        cost = chunk.get("cost_usd", 0.0)
                        tokens_in = chunk.get("input_tokens", 0)
                        tokens_out = chunk.get("output_tokens", 0)
                    if ct in ("text", "result"):
                        content_parts.append(
                            chunk.get("content", ""),
                        )
                    if ct == "tool_use":
                        tool_events.append(
                            chunk.get("tool", "unknown"),
                        )
                    yield chunk

        elapsed = (time.monotonic() - t0) * 1000
        result = PipelineResult(
            model=model,
            backend=backend.name,
            blast=blast,
            task_type=task_type,
            reason=reason,
            latency_ms=elapsed,
            cost_usd=cost,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=not has_error,
            error=error,
            fallback_used=fallback_used,
        )
        self._log_store.record(result)
        self._run_hooks(
            result, ctx, "".join(content_parts), tool_events,
        )

    def _run_hooks(
        self, result: PipelineResult, ctx: PipelineContext,
        content: str, tool_events: list[str],
    ) -> None:
        from maggy.pipeline.hooks import (
            capture_blueprint,
            record_outcome,
            record_review,
            record_spend,
        )
        record_spend(self._budget, result)
        record_outcome(self._routing, result)
        record_review(
            self._reviewer_scores, self._engram,
            result, content,
        )
        capture_blueprint(
            self._blueprints, ctx.message, result,
            tool_events, ctx.project_key,
        )

    def _find_fallback(self):
        for b in self._backends:
            if b.name == "claude":
                return b
        return None
