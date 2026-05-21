"""Parity benchmark: Cortex vs codebase-memory-mcp on maggy codebase.

These tests verify Cortex matches or exceeds codebase-memory-mcp
on the dimensions that matter for MWP.

Run with: pytest tests/test_benchmark/ -v -s
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from cortex.storage.db import CortexDB
from cortex.structure.indexer import index_project

MAGGY = Path(
    '/Users/alinaqishaheen/Documents/'
    'claude-bootstrap/maggy',
)


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


@pytest.fixture
async def indexed_db(db: CortexDB) -> CortexDB:
    await index_project(db, MAGGY)
    return db


class TestIndexingParity:
    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_index_under_3s(
        self, db: CortexDB,
    ) -> None:
        t0 = time.perf_counter()
        stats = await index_project(db, MAGGY)
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0
        assert stats['files_indexed'] >= 10
        assert stats['symbols_extracted'] >= 50

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_reindex_under_10ms(
        self, db: CortexDB,
    ) -> None:
        await index_project(db, MAGGY)
        t0 = time.perf_counter()
        stats = await index_project(db, MAGGY)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.01
        assert stats['files_indexed'] == 0


class TestSymbolSearchParity:
    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_finds_config_symbols(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT name FROM symbols '
            'WHERE name LIKE ? LIMIT 30',
            ('%config%',),
        )
        names = {r[0].lower() for r in rows}
        assert any('maggy' in n for n in names)
        assert len(rows) >= 10

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_finds_inbox_service(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT name FROM symbols '
            'WHERE name LIKE ? LIMIT 20',
            ('%inbox%',),
        )
        names = {r[0] for r in rows}
        assert 'InboxService' in names

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_finds_executor_methods(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT name FROM symbols '
            'WHERE name LIKE ? LIMIT 20',
            ('%executor%',),
        )
        names = {r[0].lower() for r in rows}
        assert any('executor' in n for n in names)

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_search_latency_under_1ms(
        self, indexed_db: CortexDB,
    ) -> None:
        t0 = time.perf_counter()
        await indexed_db.read(
            'SELECT name FROM symbols '
            'WHERE name LIKE ? LIMIT 20',
            ('%config%',),
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.001


class TestCodeSearchParity:
    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_fts_finds_config(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT file_path FROM source_fts '
            'WHERE content MATCH ? LIMIT 20',
            ('config',),
        )
        assert len(rows) >= 5

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_fts_finds_async(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT file_path FROM source_fts '
            'WHERE content MATCH ? LIMIT 20',
            ('async',),
        )
        assert len(rows) >= 3

    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_fts_latency_under_5ms(
        self, indexed_db: CortexDB,
    ) -> None:
        t0 = time.perf_counter()
        await indexed_db.read(
            'SELECT file_path FROM source_fts '
            'WHERE content MATCH ? LIMIT 20',
            ('provider',),
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.005


class TestArchitectureParity:
    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_returns_file_list(
        self, indexed_db: CortexDB,
    ) -> None:
        rows = await indexed_db.read(
            'SELECT file_path, symbol_count, language '
            'FROM file_index ORDER BY file_path',
            (),
        )
        assert len(rows) >= 10
        langs = {r[2] for r in rows}
        assert 'python' in langs


class TestDbSizeParity:
    @pytest.mark.skipif(
        not MAGGY.exists(), reason='maggy not found',
    )
    async def test_db_under_1mb(
        self, indexed_db: CortexDB,
    ) -> None:
        db_path = indexed_db.db_path
        size_kb = db_path.stat().st_size / 1024
        assert size_kb < 1024
