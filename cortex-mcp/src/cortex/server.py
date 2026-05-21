"""Cortex MCP server — FastMCP with lifespan-managed CortexDB."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .storage.db import CortexDB
from .tools.intent_impl import (
    _analyze_impl,
    _bootstrap_impl,
    _contracts_impl,
    _intent_impl,
)
from .tools.memory_impl import (
    _checkpoint_impl,
    _fatigue_impl,
    _memory_impl,
)


@asynccontextmanager
async def lifespan(
    server: FastMCP,
) -> AsyncIterator[dict[str, Any]]:
    project_dir = Path(
        os.environ.get('CORTEX_PROJECT_DIR', os.getcwd()),
    )
    db_path = project_dir / '.cortex' / 'cortex.db'
    db = CortexDB(db_path)
    await db.start()
    try:
        yield {'db': db, 'project_dir': project_dir}
    finally:
        await db.stop()


cortex = FastMCP(
    name='Cortex',
    instructions=(
        'Cortex: unified code intelligence. '
        'Structure (what), Intent (why), Memory (context). '
        '15 tools across 3 layers. '
        'Use cortex_explain for full cross-layer context.'
    ),
    lifespan=lifespan,
)

from .tools import intent_tools, memory_tools, structure_tools, unified_tools  # noqa: E402

structure_tools.register(cortex)
intent_tools.register(cortex)
memory_tools.register(cortex)
unified_tools.register(cortex)

__all__ = [
    'cortex',
    '_intent_impl',
    '_analyze_impl',
    '_bootstrap_impl',
    '_contracts_impl',
    '_memory_impl',
    '_checkpoint_impl',
    '_fatigue_impl',
]
