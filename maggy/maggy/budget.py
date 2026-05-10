"""Token budget manager — tracks spend per provider with daily limits."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from maggy.config import MaggyConfig


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS spend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spend_day
    ON spend(day, provider);
"""


class BudgetManager:
    """Track token spend per provider with daily limits."""

    def __init__(self, cfg: MaggyConfig):
        self.daily_limit = cfg.budget.daily_limit_usd
        self.warning_threshold = cfg.budget.warning_threshold
        db_dir = Path(cfg.storage.path).expanduser().parent
        self._db_path = db_dir / "budget.db"
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def record_spend(
        self, provider: str, model: str, cost_usd: float,
    ) -> None:
        """Record a spend event."""
        now = datetime.now(timezone.utc)
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO spend "
                "(provider, model, cost_usd, day, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (provider, model, cost_usd,
                 now.date().isoformat(), now.isoformat()),
            )
            conn.commit()

    def today_spend(
        self, provider: str | None = None,
    ) -> float:
        """Get total spend for today."""
        today = date.today().isoformat()
        with _connect(self._db_path) as conn:
            if provider:
                row = conn.execute(
                    "SELECT COALESCE(SUM(cost_usd), 0) "
                    "FROM spend "
                    "WHERE day = ? AND provider = ?",
                    (today, provider),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(cost_usd), 0) "
                    "FROM spend WHERE day = ?",
                    (today,),
                ).fetchone()
        return float(row[0])

    def budget_status(self) -> dict:
        """Return current budget status with warnings."""
        spent = self.today_spend()
        ratio = (
            spent / self.daily_limit
            if self.daily_limit > 0
            else 0
        )
        if ratio >= 1.0:
            status = "exhausted"
        elif ratio >= self.warning_threshold:
            status = "warning"
        else:
            status = "ok"
        return {
            "spent_today_usd": round(spent, 4),
            "daily_limit_usd": self.daily_limit,
            "utilization": round(ratio, 3),
            "status": status,
        }

    def by_provider(self) -> list[dict]:
        """Get today's spend broken down by provider."""
        today = date.today().isoformat()
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT provider, SUM(cost_usd) as total "
                "FROM spend WHERE day = ? "
                "GROUP BY provider",
                (today,),
            ).fetchall()
        return [
            {
                "provider": r["provider"],
                "spent_usd": round(r["total"], 4),
            }
            for r in rows
        ]

    def is_exhausted(
        self, provider: str | None = None,
    ) -> bool:
        """Check if daily budget is exhausted."""
        spent = self.today_spend(provider)
        return spent >= self.daily_limit
