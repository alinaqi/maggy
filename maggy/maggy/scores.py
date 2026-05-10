"""Reward table — tracks model performance per task type and blast tier.

SQLite-backed with decay so old data ages out naturally.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from maggy.config import MaggyConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    task_type TEXT NOT NULL,
    blast_tier TEXT NOT NULL,
    reward REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rewards_lookup
    ON rewards(model, task_type, blast_tier);
"""

MIN_SAMPLES = 5
DECAY_RATE = 0.95


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


class RewardTable:
    """SQLite-backed reward table with time decay."""

    def __init__(self, cfg: MaggyConfig):
        db_dir = Path(cfg.storage.path).expanduser().parent
        self._db_path = db_dir / "model_scores.db"
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def record(
        self, model: str, task_type: str,
        blast_tier: str, reward: float,
    ) -> None:
        """Record a reward observation."""
        now = datetime.now(timezone.utc).isoformat()
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO rewards "
                "(model, task_type, blast_tier, "
                "reward, recorded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (model, task_type, blast_tier, reward, now),
            )
            conn.commit()

    def best_model(
        self, task_type: str, blast_tier: str,
    ) -> str | None:
        """Return best model, or None if insufficient data."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT model, reward, recorded_at "
                "FROM rewards "
                "WHERE task_type = ? AND blast_tier = ?",
                (task_type, blast_tier),
            ).fetchall()

        if not rows:
            return None

        scores: dict[str, tuple[float, int]] = {}
        today = date.today()
        for r in rows:
            model = r["model"]
            rec_date = datetime.fromisoformat(
                r["recorded_at"],
            ).date()
            days = (today - rec_date).days
            weight = DECAY_RATE ** days
            weighted = r["reward"] * weight
            total, count = scores.get(model, (0.0, 0))
            scores[model] = (total + weighted, count + 1)

        candidates = {
            m: total / count
            for m, (total, count) in scores.items()
            if count >= MIN_SAMPLES
        }
        if not candidates:
            return None

        return max(candidates, key=candidates.get)

    def heatmap(self) -> list[dict]:
        """Return reward averages for dashboard."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT model, task_type, blast_tier, "
                "AVG(reward) as avg_reward, "
                "COUNT(*) as n "
                "FROM rewards "
                "GROUP BY model, task_type, blast_tier",
            ).fetchall()
        return [
            {
                "model": r["model"],
                "task_type": r["task_type"],
                "blast_tier": r["blast_tier"],
                "avg_reward": round(r["avg_reward"], 3),
                "samples": r["n"],
            }
            for r in rows
        ]
