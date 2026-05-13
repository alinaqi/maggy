"""Blueprint store — learns repeatable task patterns.

SQLite-backed with confidence scoring so blueprints
build trust over successful executions.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS blueprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    project_key TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL,
    tool_sequence TEXT NOT NULL,
    prompt_keywords TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    min_model TEXT NOT NULL DEFAULT 'local',
    success_count INTEGER NOT NULL DEFAULT 1,
    fail_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bp_fp
    ON blueprints(fingerprint);
CREATE INDEX IF NOT EXISTS idx_bp_project_type
    ON blueprints(project_key, task_type);
"""

_MIGRATE_PROJECT_KEY = (
    "ALTER TABLE blueprints ADD COLUMN project_key"
    " TEXT NOT NULL DEFAULT ''"
)

MIN_SAMPLES = 3
MIN_OVERLAP = 0.5
MIN_CONFIDENCE = 0.7


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


class BlueprintStore:
    """SQLite-backed blueprint store."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)
            try:
                conn.execute(_MIGRATE_PROJECT_KEY)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

    def record(
        self, fingerprint: str, task_type: str,
        tool_sequence: list[str],
        keywords: list[str],
        template: str, model: str,
        project_key: str = "",
    ) -> None:
        """Insert or increment success for a blueprint."""
        now = datetime.now(timezone.utc).isoformat()
        tools_json = json.dumps(tool_sequence)
        kw_json = json.dumps(keywords)
        with _connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM blueprints WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE blueprints SET success_count = success_count + 1, "
                    "last_used_at = ?, min_model = ? WHERE fingerprint = ?",
                    (now, model, fingerprint),
                )
            else:
                conn.execute(
                    "INSERT INTO blueprints "
                    "(fingerprint, project_key, task_type, tool_sequence, "
                    "prompt_keywords, prompt_template, min_model, "
                    "last_used_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fingerprint, project_key, task_type, tools_json,
                     kw_json, template, model, now, now),
                )
            conn.commit()

    def record_failure(self, fingerprint: str) -> None:
        """Increment fail count for a blueprint."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE blueprints SET fail_count = fail_count + 1 "
                "WHERE fingerprint = ?",
                (fingerprint,),
            )
            conn.commit()

    def match(
        self, task_type: str, keywords: list[str],
        project_key: str = "",
    ) -> dict | None:
        """Find best matching blueprint or None."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM blueprints "
                "WHERE project_key = ? AND task_type = ?",
                (project_key, task_type),
            ).fetchall()
        if not rows:
            return None
        user_set = set(keywords)
        candidates = _rank_candidates(rows, user_set)
        if not candidates:
            return None
        best, best_score = candidates[0]
        if best["success_count"] >= MIN_SAMPLES:
            return best
        if len(candidates) >= MIN_SAMPLES:
            return best
        return None

    def list_all(self, limit: int = 50) -> list[dict]:
        """Return all blueprints for display."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM blueprints "
                "ORDER BY last_used_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]


def _row_to_dict(r: sqlite3.Row) -> dict:
    """Convert Row to dict with parsed JSON fields."""
    return {
        "fingerprint": r["fingerprint"],
        "project_key": r["project_key"],
        "task_type": r["task_type"],
        "tool_sequence": json.loads(r["tool_sequence"]),
        "keywords": json.loads(r["prompt_keywords"]),
        "prompt_template": r["prompt_template"],
        "min_model": r["min_model"],
        "success_count": r["success_count"],
        "fail_count": r["fail_count"],
        "last_used_at": r["last_used_at"],
    }


def _rank_candidates(
    rows: list, user_kw: set[str],
) -> list[tuple[dict, float]]:
    """Rank blueprints by overlap * confidence, descending."""
    candidates: list[tuple[dict, float]] = []
    for r in rows:
        bp = _row_to_dict(r)
        score = _score_overlap(bp, user_kw)
        if score > 0:
            candidates.append((bp, score))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def _score_overlap(bp: dict, user_kw: set[str]) -> float:
    """Score overlap and confidence, no sample gate."""
    bp_kw = set(bp["keywords"])
    if not bp_kw:
        return 0.0
    overlap = len(user_kw & bp_kw) / len(bp_kw)
    if overlap < MIN_OVERLAP:
        return 0.0
    total = bp["success_count"] + bp["fail_count"]
    conf = bp["success_count"] / total if total else 1.0
    if conf < MIN_CONFIDENCE:
        return 0.0
    return overlap * conf
