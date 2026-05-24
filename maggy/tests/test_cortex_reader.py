"""Tests for CortexReader — read-only SQLite access to .cortex/cortex.db."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_TELOS_DIR = (
    Path(__file__).resolve().parent.parent / "plugins" / "telos"
)


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = _TELOS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("telos_models", "models.py")
IntentNode = _models.IntentNode


@pytest.fixture()
def cortex_db(tmp_path):
    """Create a minimal cortex.db with reasons + drift_events."""
    db_path = tmp_path / ".cortex" / "cortex.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE reasons (
            id TEXT PRIMARY KEY,
            goal TEXT NOT NULL,
            decision_type TEXT DEFAULT 'task',
            scope TEXT DEFAULT '[]',
            owner TEXT NOT NULL,
            status TEXT DEFAULT 'proposed',
            preconditions TEXT DEFAULT '[]',
            postconditions TEXT DEFAULT '[]',
            invariants TEXT DEFAULT '[]',
            anti_criteria TEXT DEFAULT '[]',
            parent_id TEXT,
            created_at TEXT NOT NULL,
            fulfilled_at TEXT
        );
        CREATE TABLE drift_events (
            id TEXT PRIMARY KEY,
            symbol_id TEXT NOT NULL,
            from_reason_id TEXT NOT NULL,
            severity REAL DEFAULT 0.5,
            resolved INTEGER DEFAULT 0,
            detected_at TEXT NOT NULL
        );
        CREATE TABLE symbols (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            symbol_type TEXT NOT NULL,
            language TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE edges (
            id TEXT PRIMARY KEY,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT INTO reasons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("R-1", "Add auth", "task", '["auth/"]', "alice",
         "fulfilled", '["db up"]', '["token valid"]',
         '["no crash"]', '[]', None,
         "2026-05-01", "2026-05-10"),
    )
    conn.execute(
        "INSERT INTO reasons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("R-2", "Add logging", "task", '[]', "bob",
         "proposed", '[]', '[]', '[]', '[]', None,
         "2026-05-15", None),
    )
    conn.execute(
        "INSERT INTO drift_events VALUES (?,?,?,?,?,?)",
        ("D-1", "sym-1", "R-1", 0.6, 0, "2026-05-12"),
    )
    conn.execute(
        "INSERT INTO drift_events VALUES (?,?,?,?,?,?)",
        ("D-2", "sym-2", "R-1", 0.3, 1, "2026-05-11"),
    )
    conn.execute(
        "INSERT INTO symbols VALUES (?,?,?,?,?,?)",
        ("sym-1", "validate", "auth/mid.py",
         "function", "python", "2026-05-01"),
    )
    conn.execute(
        "INSERT INTO symbols VALUES (?,?,?,?,?,?)",
        ("sym-orphan", "helper", "utils.py",
         "function", "python", "2026-05-01"),
    )
    conn.execute(
        "INSERT INTO edges VALUES (?,?,?,?,?)",
        ("E-1", "R-1", "sym-1", "CREATES", "2026-05-01"),
    )
    conn.commit()
    conn.close()
    return tmp_path


class TestCortexReaderInit:

    def test_opens_existing_db(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        assert r.available

    def test_missing_db_not_available(self, tmp_path):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(tmp_path))
        assert not r.available

    def test_read_only(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        with pytest.raises(Exception):
            r._conn.execute(
                "INSERT INTO reasons (id, goal, owner, "
                "status, created_at) VALUES "
                "('X','x','x','x','x')"
            )


class TestGetReasons:

    def test_returns_all(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        reasons = r.get_reasons()
        assert len(reasons) == 2
        assert all(
            isinstance(n, IntentNode) for n in reasons
        )

    def test_filters_by_status(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        active = r.get_reasons(status="proposed")
        assert len(active) == 1
        assert active[0].id == "R-2"


class TestGetActiveDrift:

    def test_unresolved_only(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        drift = r.get_active_drift()
        assert len(drift) == 1
        assert drift[0]["id"] == "D-1"
        assert drift[0]["severity"] == 0.6


class TestGetOrphanSymbols:

    def test_finds_orphans(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        orphans = r.get_orphan_symbols()
        names = [o["name"] for o in orphans]
        assert "helper" in names
        assert "validate" not in names


class TestGetStaleReasons:

    def test_finds_stale(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        stale = r.get_stale_reasons(days=1)
        ids = [s.id for s in stale]
        assert "R-2" in ids

    def test_fulfilled_not_stale(self, cortex_db):
        _reader = _load("cortex_reader", "cortex_reader.py")
        r = _reader.CortexReader(str(cortex_db))
        stale = r.get_stale_reasons(days=1)
        ids = [s.id for s in stale]
        assert "R-1" not in ids
