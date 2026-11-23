"""Bridge chat messages to executor pipeline."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

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
            "blast_score": decision.blast,
            "task_type": decision.task_type,
            "model": getattr(decision, "model", ""),
            "source": "chat",
            "created_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        },
    )


_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 600.0
_RUNNING = frozenset({"running"})


async def executor_stream(
    executor, decision, message: str, working_dir: str,
) -> AsyncGenerator[dict, None]:
    """Stream executor output as SSE chunks."""
    task = task_from_chat(message, decision, working_dir)
    model = getattr(decision, "model", "executor")
    logger.info("executor_stream: blast=%d type=%s model=%s", decision.blast, decision.task_type, model)
    yield {"type": "agent_status", "status": f"Executing via {model}..."}
    try:
        sid = await asyncio.wait_for(
            executor.start(task.id, mode="tdd", working_dir=working_dir, task=task),
            timeout=30,
        )
        logger.info("executor_stream: session %s started", sid)
        yield {"type": "text", "content": f"Executor session: {sid}\n"}
        async for chunk in _poll_session(executor, sid):
            yield chunk
    except asyncio.TimeoutError:
        logger.warning("executor_stream: start() timed out after 30s")
        yield {"type": "error", "content": "Executor timed out"}
    except Exception as e:
        logger.warning("executor_stream: error: %s", e)
        yield {"type": "error", "content": str(e)}


_HEARTBEAT_EVERY = 5  # heartbeat every N polls (~10s)


async def _poll_session(
    executor, sid: str,
) -> AsyncGenerator[dict, None]:
    """Poll executor session until done, yielding output."""
    state = {"start": time.monotonic(), "last_len": 0, "polls": 0}
    while time.monotonic() < state["start"] + _POLL_TIMEOUT:
        chunks, done = _poll_step(executor.get_session(sid), state)
        for chunk in chunks:
            yield chunk
        if done:
            return
        await asyncio.sleep(_POLL_INTERVAL)
    yield {"type": "error", "content": "Executor timed out"}


def _poll_step(session: dict | None, state: dict) -> tuple[list[dict], bool]:
    """One poll: new output, terminal errors or a heartbeat; True when finished."""
    if not session:
        return [{"type": "error", "content": "Session lost"}], True
    output = session.get("output", "")
    chunks = []
    if output[state["last_len"]:]:
        chunks.append({"type": "text", "content": output[state["last_len"]:][:5000]})
        state["last_len"] = len(output)
    if session.get("status", "") not in _RUNNING:
        return chunks + _terminal_chunks(session), True
    state["polls"] += 1
    if state["polls"] % _HEARTBEAT_EVERY == 0:
        elapsed = int(time.monotonic() - state["start"])
        chunks.append({"type": "agent_status", "status": f"Working... ({elapsed}s)"})
    return chunks, False


def _terminal_chunks(session: dict) -> list[dict]:
    """Error chunks for a finished session: failures and unmerged work."""
    status = session.get("status", "")
    if status == "failed":
        return [{"type": "error", "content": session.get("error", "Failed")}]
    if status == "merge_failed":
        ws = session.get("preserved_workspace", "")
        msg = f"Merge failed; your work is preserved in {ws}" if ws else session.get("error", "Merge failed")
        return [{"type": "error", "content": msg}]
    return []
