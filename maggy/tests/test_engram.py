"""Tests for Engram — record, store, retrieval, diagnostics."""

from __future__ import annotations

from pathlib import Path

from maggy.engram.diagnostics import AmnesiaProfile, diagnose
from maggy.engram.record import EngramRecord, Origin, Validity
from maggy.engram.retrieval import EngramRetrieval
from maggy.engram.store import EngramStore


class TestEngramRecord:
    def test_defaults(self):
        r = EngramRecord(
            engram_id="e1", namespace="proj-1",
            memory_type="fact", content="Python 3.11",
        )
        assert r.is_active
        assert r.origin == Origin.EXPLICIT

    def test_supersede(self):
        r = EngramRecord(
            engram_id="e1", namespace="proj-1",
            memory_type="fact", content="test",
        )
        r.supersede()
        assert not r.is_active
        assert r.validity == Validity.SUPERSEDED


class TestEngramStore:
    def test_write_and_get(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        r = EngramRecord(
            engram_id="e1", namespace="proj-1",
            memory_type="fact", content="Uses FastAPI",
        )
        store.write(r)
        result = store.get("e1")
        assert result is not None
        assert result.content == "Uses FastAPI"

    def test_get_missing(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        assert store.get("nope") is None

    def test_query_by_namespace(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="e1", namespace="proj-1",
            memory_type="fact", content="A",
        ))
        store.write(EngramRecord(
            engram_id="e2", namespace="proj-2",
            memory_type="fact", content="B",
        ))
        results = store.query(namespace="proj-1")
        assert len(results) == 1
        assert results[0].namespace == "proj-1"

    def test_query_by_type(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="e1", namespace="p",
            memory_type="fact", content="A",
        ))
        store.write(EngramRecord(
            engram_id="e2", namespace="p",
            memory_type="decision", content="B",
        ))
        results = store.query(memory_type="decision")
        assert len(results) == 1

    def test_count(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="e1", namespace="p",
            memory_type="fact", content="A",
        ))
        assert store.count() == 1
        assert store.count(namespace="p") == 1
        assert store.count(namespace="x") == 0


class TestRetrieval:
    def _seed(self, tmp_path: Path) -> EngramStore:
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="e1", namespace="proj",
            memory_type="fact", content="Uses FastAPI",
            tags=["backend", "python"],
        ))
        store.write(EngramRecord(
            engram_id="e2", namespace="proj",
            memory_type="decision", content="Chose SQLite",
            tags=["database"],
        ))
        return store

    def test_by_keyword(self, tmp_path: Path):
        store = self._seed(tmp_path)
        r = EngramRetrieval(store)
        results = r.by_keyword("FastAPI")
        assert len(results) == 1

    def test_by_tag(self, tmp_path: Path):
        store = self._seed(tmp_path)
        r = EngramRetrieval(store)
        results = r.by_tag("backend")
        assert len(results) == 1

    def test_by_type(self, tmp_path: Path):
        store = self._seed(tmp_path)
        r = EngramRetrieval(store)
        results = r.by_type("decision")
        assert len(results) == 1

    def test_recent(self, tmp_path: Path):
        store = self._seed(tmp_path)
        r = EngramRetrieval(store)
        results = r.recent()
        assert len(results) == 2


class TestDiagnostics:
    def test_empty_store(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        profile = diagnose(store)
        assert profile.health_score == 0.0

    def test_healthy_store(self, tmp_path: Path):
        store = EngramStore(tmp_path / "engram.db")
        for i, mt in enumerate(
            ["fact", "decision", "code_ref", "handoff"]
        ):
            store.write(EngramRecord(
                engram_id=f"e{i}", namespace="p",
                memory_type=mt, content=f"content {i}",
            ))
        profile = diagnose(store)
        assert profile.total_memories == 4
        assert profile.active_count == 4
        assert profile.health_score > 0.8


class TestEngramSeed:
    """Seed engrams on first boot for non-zero health."""

    def test_seed_writes_all_types(self, tmp_path: Path):
        from maggy.engram.seed import seed_if_empty
        store = EngramStore(tmp_path / "engram.db")
        seed_if_empty(store)
        profile = diagnose(store)
        assert profile.facts > 0
        assert profile.decisions > 0
        assert profile.code_refs > 0
        assert profile.handoffs > 0

    def test_seed_gives_healthy_score(self, tmp_path: Path):
        from maggy.engram.seed import seed_if_empty
        store = EngramStore(tmp_path / "engram.db")
        seed_if_empty(store)
        profile = diagnose(store)
        assert profile.health_score >= 0.8

    def test_seed_fills_missing_types(self, tmp_path: Path):
        from maggy.engram.seed import seed_if_empty
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="existing", namespace="p",
            memory_type="fact", content="already here",
        ))
        seed_if_empty(store)
        profile = diagnose(store)
        # Original fact kept, missing types seeded
        assert profile.facts >= 1
        assert profile.decisions > 0
        assert profile.code_refs > 0
        assert profile.handoffs > 0

    def test_seed_skips_when_all_types_present(self, tmp_path: Path):
        from maggy.engram.seed import seed_if_empty
        store = EngramStore(tmp_path / "engram.db")
        for i, mt in enumerate(
            ["fact", "decision", "code_ref", "handoff"],
        ):
            store.write(EngramRecord(
                engram_id=f"e{i}", namespace="p",
                memory_type=mt, content=f"c{i}",
            ))
        seed_if_empty(store)
        assert store.count() == 4
