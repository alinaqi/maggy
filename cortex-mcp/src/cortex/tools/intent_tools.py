"""Intent layer MCP tool registrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context

from .intent_impl import (
    _analyze_impl,
    _bootstrap_impl,
    _contracts_impl,
    _intent_impl,
)


def _get_db(ctx: Context) -> Any:
    return ctx.request_context['db']


def _get_project_dir(ctx: Context) -> Path:
    return ctx.request_context['project_dir']


def register(cortex: Any) -> None:
    @cortex.tool(
        name='cortex_intent',
        description=(
            'Manage ReasonNodes (why code exists). '
            'action: "create", "query", "prior_work"'
        ),
    )
    async def cortex_intent(
        action: str = 'create',
        goal: str | None = None,
        scope: str | None = None,
        owner: str | None = None,
        decision_type: str = 'task',
        file_path: str | None = None,
        ctx: Context = None,
    ) -> str:
        return await _intent_impl(
            _get_db(ctx), action, goal, scope,
            owner, decision_type, file_path,
        )

    @cortex.tool(
        name='cortex_analyze',
        description=(
            'Analyze code intent health. '
            'mode: "drift", "risk", "blast_radius"'
        ),
    )
    async def cortex_analyze(
        mode: str = 'drift',
        file_path: str | None = None,
        symbol_name: str | None = None,
        max_depth: int = 5,
        ctx: Context = None,
    ) -> str:
        return await _analyze_impl(
            _get_db(ctx), mode, file_path,
            symbol_name, max_depth,
        )

    @cortex.tool(
        name='cortex_bootstrap',
        description=(
            'Bootstrap ReasonNodes from git history. '
            'Parses commits into intents.'
        ),
    )
    async def cortex_bootstrap(
        commit_count: int = 50,
        ctx: Context = None,
    ) -> str:
        return await _bootstrap_impl(
            _get_db(ctx), _get_project_dir(ctx),
            commit_count,
        )

    @cortex.tool(
        name='cortex_contracts',
        description=(
            'Query formal contracts '
            '(pre/post/invariants) for a symbol.'
        ),
    )
    async def cortex_contracts(
        symbol_name: str,
        ctx: Context = None,
    ) -> str:
        return await _contracts_impl(
            _get_db(ctx), symbol_name,
        )
