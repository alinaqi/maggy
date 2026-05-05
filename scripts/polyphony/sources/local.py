"""Local SQLite task queue (§2).

Simple task queue backed by a SQLite database file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Task


class LocalSource:
    """File-based local task queue."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or Path("~/.polyphony/queue.db")
        self._path = Path(str(self._path).strip())
        self._init_db()

    def _init_db(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self._path))
        con.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id TEXT PRIMARY KEY,"
            "  title TEXT NOT NULL,"
            "  task_type TEXT DEFAULT 'feature',"
            "  risk TEXT DEFAULT 'low',"
            "  claimed INTEGER DEFAULT 0"
            ")"
        )
        con.commit()
        con.close()

    def add_task(
        self,
        title: str,
        task_type: str = "feature",
        risk: str = "low",
    ) -> Task:
        """Add a task to the local queue."""
        task = Task(
            title=title,
            source="local",
            source_ref="local",
            task_type=task_type,
            risk=risk,
        )
        con = sqlite3.connect(str(self._path))
        con.execute(
            "INSERT INTO tasks (id, title, task_type, risk)"
            " VALUES (?, ?, ?, ?)",
            (task.id, task.title, task.task_type, task.risk),
        )
        con.commit()
        con.close()
        return task

    def poll(self) -> list[Task]:
        """Return unclaimed tasks."""
        con = sqlite3.connect(str(self._path))
        cur = con.execute(
            "SELECT id, title, task_type, risk"
            " FROM tasks WHERE claimed = 0"
        )
        tasks = []
        for row in cur.fetchall():
            tasks.append(Task(
                id=row[0],
                title=row[1],
                source="local",
                source_ref="local",
                task_type=row[2],
                risk=row[3],
            ))
        con.close()
        return tasks

    def mark_claimed(self, task_id: str) -> None:
        """Mark a task as claimed."""
        con = sqlite3.connect(str(self._path))
        con.execute(
            "UPDATE tasks SET claimed = 1 WHERE id = ?",
            (task_id,),
        )
        con.commit()
        con.close()
