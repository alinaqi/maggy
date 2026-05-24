"""Tests for learning signal writer — dedup, isolation, async safety."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from maggy.learn._writer import _content_hash, write_signal, fire_and_forget_write


class FakeEngramStore:
    def __init__(self):
        self.written: list = []
        self._existing: dict = {}

    def get(self, engram_id: str):
        return self._existing.get(engram_id)

    def write(self, record):
        self.written.append(record)

    def add_existing(self, engram_id: str, record):
        self._existing[engram_id] = record


class FakeRecord:
    def __init__(self, *, is_active: bool = True):
        self.is_active = is_active


def test_content_hash_deterministic():
    h1 = _content_hash("chat-feedback", "hello world", "proj1")
    h2 = _content_hash("chat-feedback", "hello world", "proj1")
    assert h1 == h2


def test_content_hash_scoped_by_project():
    h1 = _content_hash("chat-feedback", "same content", "proj-a")
    h2 = _content_hash("chat-feedback", "same content", "proj-b")
    assert h1 != h2


def test_content_hash_scoped_by_namespace():
    h1 = _content_hash("chat-feedback", "same content", "proj")
    h2 = _content_hash("error-patterns", "same content", "proj")
    assert h1 != h2


@pytest.mark.asyncio
async def test_write_signal_creates_engram():
    store = FakeEngramStore()
    sig = {"content": "User correction: don't do that", "memory_type": "feedback", "confidence": 0.8, "tags": ["correction"]}
    result = await write_signal(store, "chat-feedback", sig, "myproj")
    assert result is True
    assert len(store.written) == 1
    rec = store.written[0]
    assert rec.namespace == "chat-feedback"
    assert rec.memory_type == "feedback"
    assert "project:myproj" in rec.tags


@pytest.mark.asyncio
async def test_write_signal_dedup_skips_existing():
    store = FakeEngramStore()
    sig = {"content": "same signal", "memory_type": "fact", "tags": []}
    dedup_id = _content_hash("chat-feedback", "same signal", "proj")
    store.add_existing(dedup_id, FakeRecord(is_active=True))
    result = await write_signal(store, "chat-feedback", sig, "proj")
    assert result is False
    assert len(store.written) == 0


@pytest.mark.asyncio
async def test_write_signal_allows_superseded_rewrite():
    store = FakeEngramStore()
    sig = {"content": "old signal", "memory_type": "fact", "tags": []}
    dedup_id = _content_hash("chat-feedback", "old signal", "proj")
    store.add_existing(dedup_id, FakeRecord(is_active=False))
    result = await write_signal(store, "chat-feedback", sig, "proj")
    assert result is True
    assert len(store.written) == 1


@pytest.mark.asyncio
async def test_write_signal_none_store():
    result = await write_signal(None, "chat-feedback", {"content": "x", "tags": []}, "p")
    assert result is False


@pytest.mark.asyncio
async def test_write_signal_store_raises():
    store = FakeEngramStore()
    store.write = MagicMock(side_effect=RuntimeError("db locked"))
    sig = {"content": "fail", "memory_type": "fact", "tags": []}
    result = await write_signal(store, "chat-feedback", sig, "p")
    assert result is False


@pytest.mark.asyncio
async def test_fire_and_forget_no_block():
    store = FakeEngramStore()
    sigs = [
        {"content": "sig1", "memory_type": "fact", "tags": []},
        {"content": "sig2", "memory_type": "fact", "tags": []},
    ]
    fire_and_forget_write(store, "chat-feedback", sigs, "p")
    await asyncio.sleep(0.05)
    assert len(store.written) == 2


@pytest.mark.asyncio
async def test_fire_and_forget_none_store():
    fire_and_forget_write(None, "chat-feedback", [{"content": "x", "tags": []}], "p")
    await asyncio.sleep(0.01)
