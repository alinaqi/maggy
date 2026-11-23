"""_poll_session surfaces every terminal executor status to chat users."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from maggy.services import chat_executor_bridge as bridge


async def _chunks(session: dict) -> list[dict]:
    executor = MagicMock()
    executor.get_session.return_value = session
    return [c async for c in bridge._poll_session(executor, "s1")]


@pytest.mark.asyncio
async def test_merge_failed_is_reported_with_preserved_workspace():
    session = {"status": "merge_failed", "output": "",
               "error": "Merge failed", "preserved_workspace": "/ws/s1"}
    chunks = await _chunks(session)
    errors = [c for c in chunks if c["type"] == "error"]
    assert len(errors) == 1
    assert "/ws/s1" in errors[0]["content"]


@pytest.mark.asyncio
async def test_failed_is_reported():
    chunks = await _chunks({"status": "failed", "output": "", "error": "boom"})
    assert chunks == [{"type": "error", "content": "boom"}]


@pytest.mark.asyncio
async def test_completed_is_not_an_error():
    chunks = await _chunks({"status": "completed", "output": "done"})
    assert chunks == [{"type": "text", "content": "done"}]


def test_dead_parallel_running_status_dropped():
    assert bridge._RUNNING == frozenset({"running"})
