"""SQLite storage layer for Mnemos MnemoGraph."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import CheckpointNode, FatigueState, MnemoNode, _now

MNEMOS_DIR = '.mnemos'
DB_NAME = 'mnemo.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS mnemo_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    activation_weight REAL DEFAULT 1.0,
    status TEXT DEFAULT 'active',
    origin TEXT DEFAULT 'agent_generated',
    confidence REAL DEFAULT 1.0,
    scope_tags TEXT DEFAULT '[]',
    links TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    active_constraints TEXT DEFAULT '[]',
    active_results TEXT DEFAULT '[]',
    current_subgoal TEXT DEFAULT '',
    working_memory TEXT DEFAULT '',
    fatigue_at_checkpoint REAL DEFAULT 0.0,
    git_state TEXT DEFAULT '{}',
    icpg_state TEXT,
    node_summary TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fatigue_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_utilization REAL,
    scope_scatter REAL,
    reread_ratio REAL,
    error_density REAL,
    composite_score REAL,
    state TEXT,
    computed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mnemo_type ON mnemo_nodes(type);
CREATE INDEX IF NOT EXISTS idx_mnemo_task ON mnemo_nodes(task_id);
CREATE INDEX IF NOT EXISTS idx_mnemo_status ON mnemo_nodes(status);
CREATE INDEX IF NOT EXISTS idx_mnemo_weight ON mnemo_nodes(activation_weight);
CREATE INDEX IF NOT EXISTS idx_checkpoint_task ON checkpoints(task_id);
CREATE INDEX IF NOT EXISTS idx_fatigue_time ON fatigue_log(computed_at);

CREATE TABLE IF NOT EXISTS claude_sessions (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    project_slug TEXT,
    task_id TEXT,
    model TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    turn_count INTEGER NOT NULL DEFAULT 0,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    source_path TEXT NOT NULL,
    last_line_offset INTEGER NOT NULL DEFAULT 0,
    last_ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claude_turns (
    session_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    uuid TEXT,
    parent_uuid TEXT,
    role TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    tool_use_id TEXT,
    file_path TEXT,
    is_error INTEGER NOT NULL DEFAULT 0,
    text_preview TEXT,
    correction_match INTEGER NOT NULL DEFAULT 0,
    ts TEXT NOT NULL,
    PRIMARY KEY (session_id, idx),
    FOREIGN KEY (session_id) REFERENCES claude_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS claude_haze (
    session_id TEXT PRIMARY KEY,
    correction_density REAL NOT NULL,
    redo_ratio REAL NOT NULL,
    first_try_error_rate REAL NOT NULL,
    orphan_tool_use_rate REAL NOT NULL,
    backtrack_norm REAL NOT NULL,
    composite REAL NOT NULL,
    turns_analyzed INTEGER NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES claude_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_claude_sessions_project ON claude_sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_claude_sessions_task ON claude_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_claude_turns_session ON claude_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_claude_turns_tool ON claude_turns(tool_name);
CREATE INDEX IF NOT EXISTS idx_claude_turns_file ON claude_turns(file_path);
"""


class MnemosStore:
    """SQLite-backed storage for the MnemoGraph."""

    def __init__(self, project_dir: str = '.'):
        self.project_dir = Path(project_dir).resolve()
        self.mnemos_dir = self.project_dir / MNEMOS_DIR
        self.db_path = self.mnemos_dir / DB_NAME

    def init_db(self) -> None:
        """Create .mnemos/ directory, .gitignore, and initialize schema."""
        self.mnemos_dir.mkdir(parents=True, exist_ok=True)
        gitignore = self.mnemos_dir / '.gitignore'
        if not gitignore.exists():
            gitignore.write_text('*\n')
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Apply SCHEMA idempotently — safe on new and pre-existing dbs.

        Migration-safe: SCHEMA is all `CREATE ... IF NOT EXISTS`, so calling
        this on a database created before later tables were added simply
        fills in the missing tables/indexes without touching existing data.
        """
        self.mnemos_dir.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            conn.execute('PRAGMA user_version = 1')

    def exists(self) -> bool:
        return self.db_path.exists()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    # --- MnemoNode CRUD ---

    def create_node(self, node: MnemoNode) -> str:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO mnemo_nodes
                   (id, type, task_id, content, summary, activation_weight,
                    status, origin, confidence, scope_tags, links,
                    created_at, last_accessed, access_count)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    node.id, node.type, node.task_id, node.content,
                    node.summary, node.activation_weight, node.status,
                    node.origin, node.confidence,
                    json.dumps(node.scope_tags), json.dumps(node.links),
                    node.created_at, node.last_accessed, node.access_count
                )
            )
        return node.id

    def get_node(self, node_id: str) -> MnemoNode | None:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM mnemo_nodes WHERE id = ?', (node_id,)
            ).fetchone()
        return self._row_to_node(row) if row else None

    def get_active_nodes(self, task_id: str | None = None) -> list[MnemoNode]:
        with self._conn() as conn:
            if task_id:
                rows = conn.execute(
                    "SELECT * FROM mnemo_nodes WHERE status = 'active' "
                    "AND task_id = ? ORDER BY activation_weight DESC",
                    (task_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mnemo_nodes WHERE status = 'active' "
                    "ORDER BY activation_weight DESC"
                ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_by_type(
        self, node_type: str, status: str = 'active'
    ) -> list[MnemoNode]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT * FROM mnemo_nodes WHERE type = ? AND status = ? '
                'ORDER BY activation_weight DESC',
                (node_type, status)
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def nodes_for_scope(self, scope_tags: list[str]) -> list[MnemoNode]:
        """Get active nodes whose scope_tags overlap with given tags."""
        active = self.get_active_nodes()
        return [
            n for n in active
            if set(n.scope_tags) & set(scope_tags)
        ]

    def nodes_above_weight(self, threshold: float) -> list[MnemoNode]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM mnemo_nodes WHERE status = 'active' "
                "AND activation_weight >= ? ORDER BY activation_weight DESC",
                (threshold,)
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def update_node_status(self, node_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                'UPDATE mnemo_nodes SET status = ? WHERE id = ?',
                (status, node_id)
            )

    def update_node_weight(self, node_id: str, weight: float) -> None:
        with self._conn() as conn:
            conn.execute(
                'UPDATE mnemo_nodes SET activation_weight = ? WHERE id = ?',
                (weight, node_id)
            )

    def compress_node(self, node_id: str, summary: str) -> None:
        """Compress a node: replace content with summary, set status."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE mnemo_nodes SET status = 'compressed', "
                "summary = ?, content = '' WHERE id = ?",
                (summary, node_id)
            )

    def evict_node(self, node_id: str) -> None:
        """Evict a node: set status, clear content."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE mnemo_nodes SET status = 'evicted', "
                "content = '', summary = NULL WHERE id = ?",
                (node_id,)
            )

    def touch_node(self, node_id: str) -> None:
        """Update last_accessed and increment access_count."""
        with self._conn() as conn:
            conn.execute(
                'UPDATE mnemo_nodes SET last_accessed = ?, '
                'access_count = access_count + 1 WHERE id = ?',
                (_now(), node_id)
            )

    def decay_weights(self, factor: float = 0.95) -> int:
        """Apply exponential decay to all active node weights.

        Returns count of nodes decayed.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE mnemo_nodes SET activation_weight = "
                "MAX(0.01, activation_weight * ?) "
                "WHERE status = 'active' AND type NOT IN "
                "('goal', 'constraint', 'checkpoint', 'handoff')",
                (factor,)
            )
            return cursor.rowcount

    # --- Checkpoint CRUD ---

    def save_checkpoint(self, cp: CheckpointNode) -> str:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO checkpoints
                   (id, task_id, goal, active_constraints, active_results,
                    current_subgoal, working_memory, fatigue_at_checkpoint,
                    git_state, icpg_state, node_summary, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cp.id, cp.task_id, cp.goal,
                    json.dumps(cp.active_constraints),
                    json.dumps(cp.active_results),
                    cp.current_subgoal, cp.working_memory,
                    cp.fatigue_at_checkpoint,
                    json.dumps(cp.git_state),
                    json.dumps(cp.icpg_state) if cp.icpg_state else None,
                    json.dumps(cp.node_summary),
                    cp.created_at
                )
            )
        return cp.id

    def get_latest_checkpoint(
        self, task_id: str | None = None
    ) -> CheckpointNode | None:
        with self._conn() as conn:
            if task_id:
                row = conn.execute(
                    'SELECT * FROM checkpoints WHERE task_id = ? '
                    'ORDER BY created_at DESC LIMIT 1',
                    (task_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    'SELECT * FROM checkpoints '
                    'ORDER BY created_at DESC LIMIT 1'
                ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    # --- Fatigue log ---

    def log_fatigue(self, fatigue: FatigueState) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO fatigue_log
                   (token_utilization, scope_scatter, reread_ratio,
                    error_density, composite_score, state, computed_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    fatigue.token_utilization, fatigue.scope_scatter,
                    fatigue.reread_ratio, fatigue.error_density,
                    fatigue.composite_score, fatigue.state,
                    fatigue.computed_at
                )
            )

    def get_fatigue_history(self, limit: int = 20) -> list[FatigueState]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT * FROM fatigue_log ORDER BY computed_at DESC '
                'LIMIT ?', (limit,)
            ).fetchall()
        return [self._row_to_fatigue(r) for r in rows]

    # --- Stats ---

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute(
                'SELECT COUNT(*) FROM mnemo_nodes'
            ).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM mnemo_nodes WHERE status = 'active'"
            ).fetchone()[0]
            compressed = conn.execute(
                "SELECT COUNT(*) FROM mnemo_nodes WHERE status = 'compressed'"
            ).fetchone()[0]
            evicted = conn.execute(
                "SELECT COUNT(*) FROM mnemo_nodes WHERE status = 'evicted'"
            ).fetchone()[0]
            checkpoints = conn.execute(
                'SELECT COUNT(*) FROM checkpoints'
            ).fetchone()[0]
            fatigue_entries = conn.execute(
                'SELECT COUNT(*) FROM fatigue_log'
            ).fetchone()[0]

            # Type breakdown
            type_rows = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM mnemo_nodes "
                "WHERE status = 'active' GROUP BY type"
            ).fetchall()
            by_type = {r['type']: r['cnt'] for r in type_rows}

        return {
            'total_nodes': total,
            'active': active,
            'compressed': compressed,
            'evicted': evicted,
            'checkpoints': checkpoints,
            'fatigue_entries': fatigue_entries,
            'by_type': by_type
        }

    # --- iCPG Bridge ---

    def load_from_icpg(self, icpg_store, task_id: str = 'icpg-bridge') -> dict:
        """Import active iCPG ReasonNodes as GoalNodes/ConstraintNodes.

        Returns stats: {goals_imported, constraints_imported}.
        """
        stats = {'goals_imported': 0, 'constraints_imported': 0}

        reasons = icpg_store.list_reasons()
        for reason in reasons:
            if reason.status in ('rejected', 'abandoned'):
                continue

            # ReasonNode -> GoalNode
            goal_node = MnemoNode(
                type='goal',
                task_id=task_id,
                content=f'{reason.goal} [iCPG:{reason.id[:8]}]',
                origin='loaded',
                scope_tags=reason.scope,
                confidence=1.0
            )
            self.create_node(goal_node)
            stats['goals_imported'] += 1

            # Invariants/Postconditions -> ConstraintNodes
            for inv in reason.invariants:
                cn = MnemoNode(
                    type='constraint',
                    task_id=task_id,
                    content=f'INV: {inv} [from: {reason.goal[:40]}]',
                    origin='loaded',
                    scope_tags=reason.scope,
                    links=[goal_node.id]
                )
                self.create_node(cn)
                stats['constraints_imported'] += 1

            for post in reason.postconditions:
                cn = MnemoNode(
                    type='constraint',
                    task_id=task_id,
                    content=f'POST: {post} [from: {reason.goal[:40]}]',
                    origin='loaded',
                    scope_tags=reason.scope,
                    links=[goal_node.id]
                )
                self.create_node(cn)
                stats['constraints_imported'] += 1

        return stats

    # --- Row converters ---

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> MnemoNode:
        return MnemoNode(
            id=row['id'],
            type=row['type'],
            task_id=row['task_id'],
            content=row['content'],
            summary=row['summary'],
            activation_weight=row['activation_weight'],
            status=row['status'],
            origin=row['origin'],
            confidence=row['confidence'],
            scope_tags=json.loads(row['scope_tags']),
            links=json.loads(row['links']),
            created_at=row['created_at'],
            last_accessed=row['last_accessed'],
            access_count=row['access_count']
        )

    @staticmethod
    def _row_to_checkpoint(row: sqlite3.Row) -> CheckpointNode:
        return CheckpointNode(
            id=row['id'],
            task_id=row['task_id'],
            goal=row['goal'],
            active_constraints=json.loads(row['active_constraints']),
            active_results=json.loads(row['active_results']),
            current_subgoal=row['current_subgoal'],
            working_memory=row['working_memory'],
            fatigue_at_checkpoint=row['fatigue_at_checkpoint'],
            git_state=json.loads(row['git_state']),
            icpg_state=(
                json.loads(row['icpg_state'])
                if row['icpg_state'] else None
            ),
            node_summary=json.loads(row['node_summary']),
            created_at=row['created_at']
        )

    @staticmethod
    def _row_to_fatigue(row: sqlite3.Row) -> FatigueState:
        return FatigueState(
            token_utilization=row['token_utilization'],
            scope_scatter=row['scope_scatter'],
            reread_ratio=row['reread_ratio'],
            error_density=row['error_density'],
            composite_score=row['composite_score'],
            state=row['state'],
            computed_at=row['computed_at']
        )
