"""Tests for chat-to-executor bridge."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from maggy.services.chat_executor_bridge import (
    should_route_to_executor,
    task_from_chat,
)


# -- should_route_to_executor --


def test_routes_high_blast_code():
    """Blast >= 4 + code type => executor."""
    decision = MagicMock(blast=5, task_type="code")
    assert should_route_to_executor(decision) is True


def test_routes_blast_7_feature():
    """Blast 7 + feature type => executor."""
    decision = MagicMock(blast=7, task_type="feature")
    assert should_route_to_executor(decision) is True


def test_skips_low_blast():
    """Blast < 4 => passthrough."""
    decision = MagicMock(blast=3, task_type="code")
    assert should_route_to_executor(decision) is False


def test_skips_search_any_blast():
    """Search type always passthrough."""
    decision = MagicMock(blast=8, task_type="search")
    assert should_route_to_executor(decision) is False


def test_skips_docs_any_blast():
    """Docs type always passthrough."""
    decision = MagicMock(blast=6, task_type="docs")
    assert should_route_to_executor(decision) is False


def test_skips_review_any_blast():
    """Review type always passthrough."""
    decision = MagicMock(blast=9, task_type="review")
    assert should_route_to_executor(decision) is False


# -- task_from_chat --


def test_task_from_chat_creates_task():
    """task_from_chat creates a Task with correct fields."""
    decision = MagicMock(
        blast=5, task_type="code", model="claude",
    )
    task = task_from_chat(
        "Fix the auth bug in login.py",
        decision, "/Users/ali/proj",
    )
    assert task.title == "Fix the auth bug in login.py"
    assert task.description != ""
    assert task.id.startswith("chat-")
    assert task.raw["blast"] == 5
    assert task.raw["task_type"] == "code"


def test_task_from_chat_truncates_long_title():
    """Long messages get truncated title."""
    decision = MagicMock(blast=5, task_type="code")
    msg = "x" * 200
    task = task_from_chat(msg, decision, "/tmp")
    assert len(task.title) <= 120
