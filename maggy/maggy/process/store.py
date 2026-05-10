"""SQLite persistence for process intelligence data.

Stores PR records, signals, and reports. Follows the WAL +
busy_timeout pattern from maggy/services/inbox.py.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import ProcessReport

logger = logging.getLogger(__name__)


def _connect(path: Path) -> sqlite3.Connection:
    """Open SQLite with WAL mode for concurrency."""
    db = sqlite3.connect(path, timeout=30.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


class ProcessStore:
    """SQLite store for process intelligence."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self) -> None:
        with _connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS pr_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_key TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_key TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_pr_project "
                "ON pr_data(project_key)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_report_project "
                "ON reports(project_key)"
            )

    def save_pr_data(
        self, project_key: str, data: list[dict]
    ) -> None:
        """Store raw PR data as JSON."""
        now = datetime.now(timezone.utc).isoformat()
        with _connect(self.db_path) as db:
            db.execute(
                "DELETE FROM pr_data WHERE project_key = ?",
                (project_key,),
            )
            db.execute(
                "INSERT INTO pr_data "
                "(project_key, fetched_at, payload) "
                "VALUES (?, ?, ?)",
                (project_key, now, json.dumps(data)),
            )

    def load_pr_data(
        self, project_key: str
    ) -> list[dict] | None:
        """Load cached PR data. Returns None if none."""
        with _connect(self.db_path) as db:
            row = db.execute(
                "SELECT payload FROM pr_data "
                "WHERE project_key = ? "
                "ORDER BY id DESC LIMIT 1",
                (project_key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def save_report(self, report: ProcessReport) -> None:
        """Store a generated report."""
        payload = {
            "project_key": report.project_key,
            "generated_at": report.generated_at,
            "total_prs": report.total_prs,
            "summary": report.summary,
            "preemptive_fixes": report.preemptive_fixes,
            "routing_recommendations": (
                report.routing_recommendations
            ),
        }
        if report.velocity:
            payload["velocity"] = {
                "avg_time_to_merge_hours": (
                    report.velocity.avg_time_to_merge_hours
                ),
                "median_time_to_merge_hours": (
                    report.velocity.median_time_to_merge_hours
                ),
                "avg_review_rounds": (
                    report.velocity.avg_review_rounds
                ),
                "avg_pr_size": report.velocity.avg_pr_size,
                "total_prs_analyzed": (
                    report.velocity.total_prs_analyzed
                ),
            }
        if report.review_signals:
            payload["review_signals"] = [
                {
                    "reviewer": s.reviewer,
                    "theme": s.theme,
                    "count": s.count,
                }
                for s in report.review_signals[:10]
            ]
        if report.ci_signals:
            payload["ci_signals"] = [
                {
                    "check_name": s.check_name,
                    "failure_rate": round(s.failure_rate, 3),
                    "failure_count": s.failure_count,
                }
                for s in report.ci_signals[:10]
            ]

        with _connect(self.db_path) as db:
            db.execute(
                "INSERT INTO reports "
                "(project_key, generated_at, payload) "
                "VALUES (?, ?, ?)",
                (
                    report.project_key,
                    report.generated_at,
                    json.dumps(payload),
                ),
            )

    def load_latest_report(
        self, project_key: str
    ) -> dict | None:
        """Load the most recent report for a project."""
        with _connect(self.db_path) as db:
            row = db.execute(
                "SELECT payload FROM reports "
                "WHERE project_key = ? "
                "ORDER BY id DESC LIMIT 1",
                (project_key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])
