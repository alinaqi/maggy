"""Memory layer MCP tool registrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context

from .memory_impl import (
    _checkpoint_impl,
    _fatigue_impl,
    _memory_impl,
)


def _get_db(ctx: Context) -> Any:
    return ctx.request_context['db']


def _get_project_dir(ctx: Context) -> Path:
    return ctx.request_context['project_dir']


def register(cortex: Any) -> None:
    @cortex.tool(
        name='cortex_memory',
        description=(
            'Manage memory nodes (Mnemos). '
            'action: "add", "query", "consolidate"'
        ),
    )
    async def cortex_memory(
        action: str = 'add',
        node_type: str | None = None,
        task_id: str | None = None,
        content: str | None = None,
        scope_tags: str | None = None,
        min_weight: float | None = None,
        ctx: Context = None,
    ) -> str:
        return await _memory_impl(
            _get_db(ctx), action, node_type, task_id,
            content, scope_tags, min_weight,
        )

    @cortex.tool(
        name='cortex_checkpoint',
        description=(
            'Session checkpoint management. '
            'action: "write", "resume"'
        ),
    )
    async def cortex_checkpoint(
        action: str = 'write',
        task_id: str | None = None,
        goal: str | None = None,
        ctx: Context = None,
    ) -> str:
        return await _checkpoint_impl(
            _get_db(ctx), action, task_id, goal,
            _get_project_dir(ctx),
        )

    @cortex.tool(
        name='cortex_fatigue',
        description='Get latest cognitive fatigue metrics.',
    )
    async def cortex_fatigue(ctx: Context = None) -> str:
        return await _fatigue_impl(_get_db(ctx))
