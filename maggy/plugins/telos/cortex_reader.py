"""Read-only SQLite access to .cortex/cortex.db."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import importlib.util
import sys

def _sibling_import(name: str, filename: str):
    """Import a sibling module from the same directory."""
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_models = _sibling_import("telos_models", "models.py")
IntentNode = _models.IntentNode


class CortexReader:
    """Sync, read-only access to Cortex database."""

    def __init__(self, working_dir: str):
        db_path = Path(working_dir) / ".cortex" / "cortex.db"
        self._available = db_path.is_file()
        self._conn: sqlite3.Connection | None = None
        if self._available:
            self._conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA query_only = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._ensure_anti_criteria()

    @property
    def available(self) -> bool:
        return self._available

    def _ensure_anti_criteria(self) -> None:
        """Check if anti_criteria column exists."""
        if not self._conn:
            return
        cols = {
            r[1] for r in
            self._conn.execute("PRAGMA table_info(reasons)")
        }
        self._has_anti_criteria = "anti_criteria" in cols

    def get_reasons(
        self, status: str | None = None,
    ) -> list[IntentNode]:
        if not self._conn:
            return []
        if status:
            rows = self._conn.execute(
                "SELECT * FROM reasons WHERE status = ?",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM reasons",
            ).fetchall()
        return [IntentNode.from_dict(dict(r)) for r in rows]

    def get_active_drift(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM drift_events WHERE resolved = 0",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_orphan_symbols(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT s.* FROM symbols s "
            "LEFT JOIN edges e ON s.id = e.to_id "
            "WHERE e.id IS NULL",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stale_reasons(self, days: int = 7) -> list[IntentNode]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM reasons "
            "WHERE status = 'proposed' "
            "AND fulfilled_at IS NULL "
            "AND created_at <= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchall()
        return [IntentNode.from_dict(dict(r)) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
