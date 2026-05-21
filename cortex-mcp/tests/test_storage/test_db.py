"""Tests for CortexDB — async SQLite with writer thread + reader pool."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cortex.storage.db import CortexDB


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


class TestCortexDBLifecycle:
    async def test_start_creates_schema(self, db: CortexDB) -> None:
        rows = await db.read('SELECT name FROM sqlite_master WHERE type = ?', ('table',))
        table_names = {r[0] for r in rows}
        assert 'symbols' in table_names
        assert 'edges' in table_names
        assert 'reasons' in table_names
        assert 'mnemo_nodes' in table_names
        assert 'file_index' in table_names
        assert 'checkpoints' in table_names
        assert 'fatigue_log' in table_names
        assert 'projects' in table_names
        assert '_migrations' in table_names

    async def test_db_file_exists(self, db: CortexDB) -> None:
        assert db.db_path.exists()

    async def test_wal_mode_enabled(self, db: CortexDB) -> None:
        rows = await db.read('PRAGMA journal_mode', ())
        assert rows[0][0] == 'wal'

    async def test_foreign_keys_enabled(self, db: CortexDB) -> None:
        rows = await db.read('PRAGMA foreign_keys', ())
        assert rows[0][0] == 1


class TestCortexDBWrites:
    async def test_write_and_read(self, db: CortexDB) -> None:
        await db.write(
            "INSERT INTO symbols (id, name, file_path, symbol_type, language, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('sym-1', 'main', 'src/main.py', 'function', 'python', '2026-01-01T00:00:00Z'),
        )
        rows = await db.read("SELECT name FROM symbols WHERE id = ?", ('sym-1',))
        assert len(rows) == 1
        assert rows[0][0] == 'main'

    async def test_write_batch(self, db: CortexDB) -> None:
        statements = [
            (
                "INSERT INTO symbols (id, name, file_path, symbol_type, language, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f'sym-{i}', f'func_{i}', 'src/main.py', 'function', 'python', '2026-01-01'),
            )
            for i in range(100)
        ]
        await db.write_batch(statements)
        rows = await db.read("SELECT COUNT(*) FROM symbols", ())
        assert rows[0][0] == 100

    async def test_concurrent_reads(self, db: CortexDB) -> None:
        await db.write(
            "INSERT INTO symbols (id, name, file_path, symbol_type, language, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('sym-1', 'main', 'src/main.py', 'function', 'python', '2026-01-01'),
        )
        results = await asyncio.gather(
            db.read("SELECT name FROM symbols WHERE id = ?", ('sym-1',)),
            db.read("SELECT name FROM symbols WHERE id = ?", ('sym-1',)),
            db.read("SELECT name FROM symbols WHERE id = ?", ('sym-1',)),
        )
        assert all(len(r) == 1 for r in results)
        assert all(r[0][0] == 'main' for r in results)

    async def test_write_serialization(self, db: CortexDB) -> None:
        """Multiple concurrent writes should not cause SQLITE_BUSY."""
        tasks = []
        for i in range(50):
            tasks.append(
                db.write(
                    "INSERT INTO symbols (id, name, file_path, symbol_type, language, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (f'sym-{i}', f'func_{i}', 'src/main.py', 'function', 'python', '2026-01-01'),
                )
            )
        await asyncio.gather(*tasks)
        rows = await db.read("SELECT COUNT(*) FROM symbols", ())
        assert rows[0][0] == 50


class TestCortexDBSchema:
    async def test_schema_version(self, db: CortexDB) -> None:
        rows = await db.read('PRAGMA user_version', ())
        assert rows[0][0] >= 1

    async def test_symbols_has_line_columns(self, db: CortexDB) -> None:
        info = await db.read("PRAGMA table_info(symbols)", ())
        col_names = {r[1] for r in info}
        assert 'line_start' in col_names
        assert 'line_end' in col_names
        assert 'docstring' in col_names
        assert 'is_pinned' in col_names

    async def test_edges_has_layer_column(self, db: CortexDB) -> None:
        info = await db.read("PRAGMA table_info(edges)", ())
        col_names = {r[1] for r in info}
        assert 'layer' in col_names
        assert 'from_type' in col_names
        assert 'to_type' in col_names

    async def test_file_index_has_stat_columns(self, db: CortexDB) -> None:
        info = await db.read("PRAGMA table_info(file_index)", ())
        col_names = {r[1] for r in info}
        assert 'mtime_ns' in col_names
        assert 'size' in col_names
        assert 'checksum' in col_names

    async def test_mnemo_nodes_has_pinned(self, db: CortexDB) -> None:
        info = await db.read("PRAGMA table_info(mnemo_nodes)", ())
        col_names = {r[1] for r in info}
        assert 'is_pinned' in col_names

    async def test_pending_eviction_table_exists(self, db: CortexDB) -> None:
        rows = await db.read(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('pending_eviction',),
        )
        assert len(rows) == 1
