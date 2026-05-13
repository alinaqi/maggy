"""Bridge chat messages to executor pipeline."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

_PASSTHROUGH_TYPES = frozenset({"search", "docs", "review"})
_BLAST_THRESHOLD = 4


def should_route_to_executor(decision) -> bool:
    """Check if a routing decision should use executor."""
    if decision.task_type in _PASSTHROUGH_TYPES:
        return False
    return decision.blast >= _BLAST_THRESHOLD


def task_from_chat(
    message: str, decision, working_dir: str,
):
    """Create ephemeral Task from chat message."""
    from maggy.providers.base import Task
    title = message[:120]
    return Task(
        id=f"chat-{uuid.uuid4().hex[:8]}",
        title=title,
        description=message,
        status="open",
        raw={
            "blast": decision.blast,
            "task_type": decision.task_type,
            "model": getattr(decision, "model", ""),
            "source": "chat",
            "created_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        },
    )


_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 300.0
_RUNNING = frozenset({"running", "parallel_running"})


async def executor_stream(
    executor, decision, message: str, working_dir: str,
) -> AsyncGenerator[dict, None]:
    """Stream executor output as SSE chunks."""
    task = task_from_chat(message, decision, working_dir)
    model = getattr(decision, "model", "executor")
    yield {"type": "agent_status", "status": f"Executing via {model}..."}
    try:
        sid = await asyncio.wait_for(
            executor.start(task.id, mode="tdd", working_dir=working_dir, task=task),
            timeout=30,
        )
        yield {"type": "text", "content": f"Executor session: {sid}\n"}
        async for chunk in _poll_session(executor, sid):
            yield chunk
    except asyncio.TimeoutError:
        yield {"type": "error", "content": "Executor timed out"}
    except Exception as e:
        yield {"type": "error", "content": str(e)}


async def _poll_session(
    executor, sid: str,
) -> AsyncGenerator[dict, None]:
    """Poll executor session until done, yielding output."""
    import time
    deadline = time.monotonic() + _POLL_TIMEOUT
    last_len = 0
    while time.monotonic() < deadline:
        session = executor.get_session(sid)
        if not session:
            yield {"type": "error", "content": "Session lost"}
            return
        output = session.get("output", "")
        new = output[last_len:]
        if new:
            yield {"type": "text", "content": new[:5000]}
            last_len = len(output)
        status = session.get("status", "")
        if status not in _RUNNING:
            if status == "failed":
                yield {"type": "error", "content": session.get("error", "Failed")}
            return
        await asyncio.sleep(_POLL_INTERVAL)
    yield {"type": "error", "content": "Executor timed out"}
