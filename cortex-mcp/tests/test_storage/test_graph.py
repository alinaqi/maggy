"""Tests for graph traversal — trace_path direction + dedup."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.storage.db import CortexDB
from cortex.storage.graph import trace_path


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


async def _seed_graph(db: CortexDB) -> None:
    """A -> B -> C, with CALLS edges."""
    now = '2024-01-01T00:00:00Z'
    for name, sid in [('A', 'a1'), ('B', 'b1'), ('C', 'c1')]:
        await db.write(
            'INSERT INTO symbols (id, name, file_path, symbol_type, '
            'language, checksum, created_at) VALUES (?,?,?,?,?,?,?)',
            (sid, name, 'test.py', 'function', 'python', 'x', now),
        )
    await db.write(
        'INSERT INTO edges (id, from_id, from_type, to_id, to_type, '
        'edge_type, layer, created_at) VALUES (?,?,?,?,?,?,?,?)',
        ('e1', 'a1', 'symbol', 'b1', 'symbol', 'CALLS', 'structure', now),
    )
    await db.write(
        'INSERT INTO edges (id, from_id, from_type, to_id, to_type, '
        'edge_type, layer, created_at) VALUES (?,?,?,?,?,?,?,?)',
        ('e2', 'b1', 'symbol', 'c1', 'symbol', 'CALLS', 'structure', now),
    )


class TestTraceDirection:
    async def test_out_direction(self, db: CortexDB) -> None:
        await _seed_graph(db)
        results = await trace_path(db, 'A', direction='out')
        names = [r['name'] for r in results]
        assert 'B' in names
        assert 'C' in names

    async def test_in_direction(self, db: CortexDB) -> None:
        await _seed_graph(db)
        results = await trace_path(db, 'C', direction='in')
        names = [r['name'] for r in results]
        assert 'B' in names

    async def test_both_direction(self, db: CortexDB) -> None:
        await _seed_graph(db)
        results = await trace_path(db, 'B', direction='both')
        names = [r['name'] for r in results]
        assert 'A' in names
        assert 'C' in names

    async def test_default_is_out(self, db: CortexDB) -> None:
        await _seed_graph(db)
        out = await trace_path(db, 'A', direction='out')
        default = await trace_path(db, 'A')
        assert [r['name'] for r in out] == [r['name'] for r in default]

    async def test_distinct_results(self, db: CortexDB) -> None:
        await _seed_graph(db)
        results = await trace_path(db, 'A', direction='out')
        ids = [r['id'] for r in results if r['depth'] > 0]
        assert len(ids) == len(set(ids))

    async def test_to_symbol_filter(self, db: CortexDB) -> None:
        await _seed_graph(db)
        results = await trace_path(
            db, 'A', direction='out', to_symbol='C',
        )
        assert all(r['name'] == 'C' for r in results if r['depth'] > 0)
