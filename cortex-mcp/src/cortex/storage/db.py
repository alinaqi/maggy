"""CortexDB — sync sqlite3 with dedicated writer thread + reader pool.

Architecture (per DeepSeek Pro review):
- Single writer thread consuming an asyncio.Queue (no SQLITE_BUSY)
- 4 reader connections in round-robin (concurrent reads via run_in_executor)
- WAL mode, NORMAL sync, 4GB cache on all connections
"""

from __future__ import annotations

import asyncio
import queue
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import INDEXES_DDL, SCHEMA_DDL, SCHEMA_VERSION

type Row = tuple[Any, ...]


def _configure_conn(conn: sqlite3.Connection) -> None:
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-4000000')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA auto_vacuum=INCREMENTAL')


class CortexDB:
    """Async interface over sync sqlite3 with serialized writes."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._write_queue: queue.Queue[
            tuple[str, tuple[Any, ...], asyncio.Future[Any]] | None
        ] = queue.Queue()
        self._batch_queue: queue.Queue[
            tuple[list[tuple[str, tuple[Any, ...]]], asyncio.Future[None]] | None
        ] = queue.Queue()
        self._writer_conn: sqlite3.Connection | None = None
        self._reader_pool: list[sqlite3.Connection] = []
        self._writer_thread: threading.Thread | None = None
        self._running = False
        self._reader_idx = 0

    async def start(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._writer_conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        _configure_conn(self._writer_conn)

        self._reader_pool = [
            sqlite3.connect(str(self.db_path), check_same_thread=False)
            for _ in range(4)
        ]
        for conn in self._reader_pool:
            _configure_conn(conn)

        self._init_schema()

        self._running = True
        self._writer_thread = threading.Thread(
            target=self._write_loop, daemon=True, name='cortex-writer'
        )
        self._writer_thread.start()

    async def stop(self) -> None:
        self._running = False
        self._write_queue.put(None)
        self._batch_queue.put(None)
        if self._writer_thread:
            self._writer_thread.join(timeout=5.0)
        if self._writer_conn:
            self._writer_conn.close()
        for conn in self._reader_pool:
            conn.close()
        self._reader_pool.clear()

    async def read(self, sql: str, params: tuple[Any, ...] = ()) -> list[Row]:
        loop = asyncio.get_running_loop()
        conn = self._get_reader()
        return await loop.run_in_executor(
            None, lambda: conn.execute(sql, params).fetchall()
        )

    async def write(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._write_queue.put((sql, params, future))
        return await future

    async def write_batch(
        self, statements: list[tuple[str, tuple[Any, ...]]]
    ) -> None:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        self._batch_queue.put((statements, future))
        return await future

    def _get_reader(self) -> sqlite3.Connection:
        idx = self._reader_idx % len(self._reader_pool)
        self._reader_idx += 1
        return self._reader_pool[idx]

    def _write_loop(self) -> None:
        assert self._writer_conn is not None
        while self._running:
            self._process_single_writes()
            self._process_batch_writes()

    def _process_single_writes(self) -> None:
        assert self._writer_conn is not None
        try:
            item = self._write_queue.get(timeout=0.05)
        except queue.Empty:
            return
        if item is None:
            return
        sql, params, future = item
        try:
            self._writer_conn.execute(sql, params)
            self._writer_conn.commit()
            future.get_loop().call_soon_threadsafe(future.set_result, None)
        except Exception as e:
            future.get_loop().call_soon_threadsafe(future.set_exception, e)

    def _process_batch_writes(self) -> None:
        assert self._writer_conn is not None
        try:
            item = self._batch_queue.get_nowait()
        except queue.Empty:
            return
        if item is None:
            return
        statements, future = item
        try:
            for sql, params in statements:
                self._writer_conn.execute(sql, params)
            self._writer_conn.commit()
            future.get_loop().call_soon_threadsafe(future.set_result, None)
        except Exception as e:
            self._writer_conn.rollback()
            future.get_loop().call_soon_threadsafe(future.set_exception, e)

    def _init_schema(self) -> None:
        assert self._writer_conn is not None
        current_version = self._writer_conn.execute(
            'PRAGMA user_version'
        ).fetchone()[0]

        if current_version < SCHEMA_VERSION:
            self._writer_conn.executescript(SCHEMA_DDL)
            self._writer_conn.executescript(INDEXES_DDL)
            self._writer_conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')

            now = datetime.now(timezone.utc).isoformat()
            self._writer_conn.execute(
                'INSERT OR IGNORE INTO _migrations (version, applied_at, description) '
                'VALUES (?, ?, ?)',
                (SCHEMA_VERSION, now, 'Initial schema'),
            )
            self._writer_conn.commit()
