"""Daily budget ledger: reserve before launch, settle or release after (RFC §2.6.4).

Every reservation runs in one `BEGIN IMMEDIATE` transaction, so concurrent runners
(threads or processes) serialise on the write lock and never overshoot per_day_usd.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from maggy.worker.launch import Refused

SCHEMA = """CREATE TABLE IF NOT EXISTS reservations (
    run_id TEXT PRIMARY KEY, day TEXT NOT NULL, reserved REAL NOT NULL,
    actual REAL, status TEXT NOT NULL)"""
DAY_TOTAL = """SELECT COALESCE(SUM(CASE status WHEN 'reserved' THEN reserved
    WHEN 'settled' THEN actual ELSE 0 END), 0) FROM reservations WHERE day = ?"""
EPSILON = 1e-9


class BudgetRefused(Refused):
    """A reservation would exceed per_day_usd; the worker must not launch."""


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


class BudgetLedger:
    def __init__(self, path: Path | None = None, per_day_usd: float | None = None) -> None:
        self.path = path or Path.home() / ".maggy" / "budget.db"
        self.per_day_usd = per_day_usd

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=30.0, isolation_level=None)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(SCHEMA)
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def reserve(self, run_id: str, amount: float) -> None:
        """Reserve `amount` for `run_id`, or raise BudgetRefused over the daily cap."""
        if amount < 0:
            raise ValueError(f"reservation must be >= 0, got {amount}")
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM reservations WHERE run_id = ?", (run_id,)).fetchone():
                raise ValueError(f"run {run_id!r} already has a reservation")
            spent = conn.execute(DAY_TOTAL, (_today(),)).fetchone()[0]
            cap = self.per_day_usd
            if cap is not None and spent + amount > cap + EPSILON:
                raise BudgetRefused(f"reserving ${amount:.2f} would exceed per_day_usd "
                                    f"${cap:.2f} (${spent:.2f} already committed today)")
            conn.execute("INSERT INTO reservations VALUES (?, ?, ?, NULL, 'reserved')",
                         (run_id, _today(), amount))

    def settle(self, run_id: str, actual: float) -> None:
        """Replace the open reservation with the run's actual cost."""
        self._close(run_id, "settled", actual)

    def release(self, run_id: str) -> None:
        """Drop the open reservation (the run never spent anything)."""
        self._close(run_id, "released", None)

    def _close(self, run_id: str, status: str, actual: float | None) -> None:
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE reservations SET status = ?, actual = ? "
                "WHERE run_id = ? AND status = 'reserved'", (status, actual, run_id))
            if cursor.rowcount == 0:
                raise KeyError(f"no open reservation for run {run_id!r}")

    def spent_today(self) -> float:
        """Reserved plus settled spend for the current UTC day."""
        with self._transaction() as conn:
            return float(conn.execute(DAY_TOTAL, (_today(),)).fetchone()[0])
