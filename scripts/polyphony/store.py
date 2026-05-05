"""SQLite storage layer for Polyphony."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Result, RunSpec, Task, _now

DB_NAME = "orchestrator.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'discovered',
    task_type TEXT DEFAULT 'feature',
    scope TEXT DEFAULT '[]',
    risk TEXT DEFAULT 'low',
    context_tokens INTEGER DEFAULT 0,
    requires_web INTEGER DEFAULT 0,
    run_spec_id TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_specs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    identity TEXT NOT NULL,
    workspace TEXT NOT NULL,
    image TEXT NOT NULL,
    attempt INTEGER DEFAULT 1,
    model TEXT DEFAULT '',
    fallback TEXT DEFAULT '[]',
    max_turns INTEGER DEFAULT 25,
    allowed_paths TEXT DEFAULT '[]',
    proof_of_work TEXT DEFAULT '[]',
    env_overlay TEXT DEFAULT '{}',
    volume_mounts TEXT DEFAULT '[]',
    deadline_seconds INTEGER DEFAULT 1800
);

CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_spec_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    turns INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    cost_usd REAL,
    artifacts TEXT DEFAULT '{}',
    events TEXT DEFAULT '[]',
    completed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
"""


class PolyphonyStore:
    """SQLite-backed persistence for Polyphony."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / DB_NAME

    def init_db(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._write_gitignore()
        conn = self._connect()
        conn.executescript(SCHEMA)
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _write_gitignore(self) -> None:
        gi = self.base_dir / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n")

    # --- Task CRUD ---

    def save_task(self, task: Task) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO tasks VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task.id, task.title, task.source,
                task.source_ref, task.state, task.task_type,
                json.dumps(task.scope), task.risk,
                task.context_tokens, int(task.requires_web),
                task.run_spec_id, json.dumps(task.metadata),
                task.created_at, task.updated_at,
            ),
        )
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Task | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,),
        ).fetchone()
        conn.close()
        return self._row_to_task(row) if row else None

    def list_tasks(self, state: str | None = None) -> list[Task]:
        conn = self._connect()
        if state:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE state=?", (state,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks").fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"], title=row["title"],
            source=row["source"], source_ref=row["source_ref"],
            state=row["state"], task_type=row["task_type"],
            scope=json.loads(row["scope"]), risk=row["risk"],
            context_tokens=row["context_tokens"],
            requires_web=bool(row["requires_web"]),
            run_spec_id=row["run_spec_id"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- RunSpec CRUD ---

    def save_run_spec(self, rs: RunSpec) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO run_specs VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rs.id, rs.task_id, rs.agent, rs.identity,
                rs.workspace, rs.image, rs.attempt, rs.model,
                json.dumps(rs.fallback), rs.max_turns,
                json.dumps(rs.allowed_paths),
                json.dumps(rs.proof_of_work),
                json.dumps(rs.env_overlay),
                json.dumps(rs.volume_mounts),
                rs.deadline_seconds,
            ),
        )
        conn.commit()
        conn.close()

    def get_run_spec(self, rs_id: str) -> RunSpec | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM run_specs WHERE id=?", (rs_id,),
        ).fetchone()
        conn.close()
        return self._row_to_run_spec(row) if row else None

    def _row_to_run_spec(self, row: sqlite3.Row) -> RunSpec:
        return RunSpec(
            id=row["id"], task_id=row["task_id"],
            agent=row["agent"], identity=row["identity"],
            workspace=row["workspace"], image=row["image"],
            attempt=row["attempt"], model=row["model"],
            fallback=json.loads(row["fallback"]),
            max_turns=row["max_turns"],
            allowed_paths=json.loads(row["allowed_paths"]),
            proof_of_work=json.loads(row["proof_of_work"]),
            env_overlay=json.loads(row["env_overlay"]),
            volume_mounts=json.loads(row["volume_mounts"]),
            deadline_seconds=row["deadline_seconds"],
        )

    # --- Result CRUD ---

    def save_result(self, result: Result) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO results VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            (
                result.id, result.task_id, result.run_spec_id,
                result.agent, result.status, result.turns,
                result.duration_seconds, result.cost_usd,
                json.dumps(result.artifacts),
                json.dumps(result.events),
                result.completed_at,
            ),
        )
        conn.commit()
        conn.close()

    def get_result(self, result_id: str) -> Result | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM results WHERE id=?", (result_id,),
        ).fetchone()
        conn.close()
        return self._row_to_result(row) if row else None

    def list_results(self, task_id: str) -> list[Result]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM results WHERE task_id=?",
            (task_id,),
        ).fetchall()
        conn.close()
        return [self._row_to_result(r) for r in rows]

    def _row_to_result(self, row: sqlite3.Row) -> Result:
        return Result(
            id=row["id"], task_id=row["task_id"],
            run_spec_id=row["run_spec_id"],
            agent=row["agent"], status=row["status"],
            turns=row["turns"],
            duration_seconds=row["duration_seconds"],
            cost_usd=row["cost_usd"],
            artifacts=json.loads(row["artifacts"]),
            events=json.loads(row["events"]),
            completed_at=row["completed_at"],
        )

    # --- State log ---

    def log_transition(self, task_id: str, from_s: str, to_s: str) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT INTO state_log (task_id, from_state, to_state, timestamp) "
            "VALUES (?,?,?,?)",
            (task_id, from_s, to_s, _now()),
        )
        conn.commit()
        conn.close()

    def get_state_log(self, task_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM state_log WHERE task_id=? "
            "ORDER BY id",
            (task_id,),
        ).fetchall()
        conn.close()
        return [
            {
                "from_state": r["from_state"],
                "to_state": r["to_state"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
