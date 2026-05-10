"""Tests for mesh SQLite store."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.mesh.store import MeshStore


@pytest.fixture
def store(tmp_path: Path) -> MeshStore:
    return MeshStore(tmp_path / "mesh.db")


class TestPeerCRUD:
    def test_upsert_and_get(self, store: MeshStore):
        store.upsert_peer("p1", "Alice", "1.2.3.4", 8080, "acme")
        peer = store.get_peer("p1", "acme")
        assert peer is not None
        assert peer["name"] == "Alice"

    def test_list_by_org(self, store: MeshStore):
        store.upsert_peer("p1", "A", "1.1.1.1", 8080, "acme")
        store.upsert_peer("p2", "B", "2.2.2.2", 8080, "other")
        acme = store.list_peers(org="acme")
        assert len(acme) == 1

    def test_list_all(self, store: MeshStore):
        store.upsert_peer("p1", "A", "1.1.1.1", 8080, "a")
        store.upsert_peer("p2", "B", "2.2.2.2", 8080, "b")
        assert len(store.list_peers()) == 2

    def test_remove_peer(self, store: MeshStore):
        store.upsert_peer("p1", "A", "1.1.1.1", 8080, "acme")
        assert store.remove_peer("p1", "acme")
        assert store.get_peer("p1", "acme") is None

    def test_remove_missing(self, store: MeshStore):
        assert not store.remove_peer("nope", "acme")

    def test_upsert_updates(self, store: MeshStore):
        store.upsert_peer("p1", "A", "1.1.1.1", 8080, "acme")
        store.upsert_peer("p1", "A-new", "9.9.9.9", 8080, "acme")
        peer = store.get_peer("p1", "acme")
        assert peer["name"] == "A-new"
        assert peer["address"] == "9.9.9.9"


class TestMemoryCRUD:
    def test_write_and_list(self, store: MeshStore):
        store.write_memory("acme", "k1", "score", {"x": 1}, "p1")
        mems = store.list_memories("acme")
        assert len(mems) == 1
        assert mems[0]["key"] == "k1"

    def test_scoped_by_org(self, store: MeshStore):
        store.write_memory("acme", "k1", "score", {}, "p1")
        store.write_memory("other", "k2", "gap", {}, "p2")
        assert len(store.list_memories("acme")) == 1
        assert len(store.list_memories("other")) == 1

    def test_upsert_memory(self, store: MeshStore):
        store.write_memory("acme", "k1", "score", {"v": 1}, "p1")
        store.write_memory("acme", "k1", "score", {"v": 2}, "p1")
        mems = store.list_memories("acme")
        assert len(mems) == 1
        assert mems[0]["content"]["v"] == 2


class TestQuarantineCRUD:
    def test_quarantine_and_list(self, store: MeshStore):
        store.quarantine_item("acme", "k1", "p1", "low conf", {"x": 1})
        items = store.list_quarantined("acme")
        assert len(items) == 1
        assert items[0]["reason"] == "low conf"

    def test_promote(self, store: MeshStore):
        store.quarantine_item("acme", "k1", "p1", "test", {})
        assert store.promote_item("acme", "k1")
        assert len(store.list_quarantined("acme")) == 0

    def test_promote_missing(self, store: MeshStore):
        assert not store.promote_item("acme", "nope")

    def test_scoped_by_org(self, store: MeshStore):
        store.quarantine_item("acme", "k1", "p1", "r", {})
        store.quarantine_item("other", "k2", "p2", "r", {})
        assert len(store.list_quarantined("acme")) == 1
