"""Tests for learning memory consolidator."""

from __future__ import annotations

import pytest

from maggy.learn.consolidator import (
    DECAY_FACTOR,
    EXPIRE_THRESHOLD,
    MAX_PER_NAMESPACE,
    consolidate,
    consolidate_all,
)


class FakeRecord:
    def __init__(self, engram_id: str, confidence: float = 1.0, tags: list | None = None):
        self.engram_id = engram_id
        self.confidence = confidence
        self.tags = tags or []
        self.validity = "active"
        self.is_active = True
        self.namespace = "test"

    def supersede(self):
        self.validity = "superseded"
        self.is_active = False


class FakeStore:
    def __init__(self, records: list[FakeRecord] | None = None):
        self._records = {r.engram_id: r for r in (records or [])}

    def query(self, namespace: str = "", active_only: bool = True, limit: int = 1000) -> list:
        recs = list(self._records.values())
        if active_only:
            recs = [r for r in recs if r.is_active]
        return recs[:limit]

    def write(self, record):
        self._records[record.engram_id] = record


def test_decay_reduces_confidence():
    r = FakeRecord("a", confidence=1.0)
    store = FakeStore([r])
    consolidate(store, "test")
    assert r.confidence == round(1.0 * DECAY_FACTOR, 4)


def test_expire_low_confidence():
    r = FakeRecord("a", confidence=0.05)
    store = FakeStore([r])
    stats = consolidate(store, "test")
    assert r.validity == "superseded"
    assert stats["expired"] >= 1


def test_evict_over_cap():
    records = [FakeRecord(f"r{i}", confidence=0.5) for i in range(MAX_PER_NAMESPACE + 50)]
    store = FakeStore(records)
    stats = consolidate(store, "test")
    active = [r for r in store._records.values() if r.is_active]
    assert len(active) <= MAX_PER_NAMESPACE


def test_no_eviction_under_cap():
    records = [FakeRecord(f"r{i}", confidence=0.9) for i in range(10)]
    store = FakeStore(records)
    stats = consolidate(store, "test")
    assert stats["evicted"] == 0


def test_empty_store():
    store = FakeStore([])
    stats = consolidate(store, "test")
    assert stats["decayed"] == 0
    assert stats["expired"] == 0
    assert stats["evicted"] == 0


def test_consolidate_all_runs_all_namespaces():
    store = FakeStore([FakeRecord("a", confidence=0.8, tags=["chat"])])
    results = consolidate_all(store)
    assert "chat-feedback" in results
    assert "error-patterns" in results
    assert "review-feedback" in results
    assert "pr-feedback" in results
