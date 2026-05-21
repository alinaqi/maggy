"""Cortex unified SQLite schema — structure + intent + memory in one DB."""

from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_DDL = """
-- ============================================================
-- Structure layer
-- ============================================================

CREATE TABLE IF NOT EXISTS projects (
    path TEXT PRIMARY KEY,
    name TEXT,
    languages TEXT DEFAULT '[]',
    file_count INTEGER DEFAULT 0,
    symbol_count INTEGER DEFAULT 0,
    last_indexed TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_index (
    file_path TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    language TEXT,
    mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL,
    checksum TEXT NOT NULL,
    symbol_count INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0,
    last_indexed TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    language TEXT NOT NULL,
    signature TEXT,
    checksum TEXT,
    line_start INTEGER,
    line_end INTEGER,
    docstring TEXT,
    is_pinned INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL,
    from_type TEXT NOT NULL,
    to_id TEXT NOT NULL,
    to_type TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    layer TEXT DEFAULT 'structure',
    confidence REAL DEFAULT 1.0,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS adrs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'proposed',
    context TEXT,
    decision TEXT,
    consequences TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- ============================================================
-- Intent layer (iCPG)
-- ============================================================

CREATE TABLE IF NOT EXISTS reasons (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    decision_type TEXT DEFAULT 'task',
    scope TEXT DEFAULT '[]',
    owner TEXT NOT NULL,
    agent TEXT,
    status TEXT DEFAULT 'proposed',
    source TEXT DEFAULT 'manual',
    task_id TEXT,
    parent_id TEXT REFERENCES reasons(id),
    preconditions TEXT DEFAULT '[]',
    postconditions TEXT DEFAULT '[]',
    invariants TEXT DEFAULT '[]',
    is_pinned INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    fulfilled_at TEXT
);

CREATE TABLE IF NOT EXISTS drift_events (
    id TEXT PRIMARY KEY,
    symbol_id TEXT NOT NULL,
    from_reason_id TEXT NOT NULL,
    drift_dimensions TEXT DEFAULT '[]',
    severity REAL DEFAULT 0.5,
    description TEXT,
    resolved INTEGER DEFAULT 0,
    detected_at TEXT NOT NULL
);

-- ============================================================
-- Memory layer (Mnemos)
-- ============================================================

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
    is_pinned INTEGER DEFAULT 0,
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
    task_narrative TEXT DEFAULT '',
    recent_files TEXT DEFAULT '[]',
    fatigue_at_checkpoint REAL DEFAULT 0.0,
    git_state TEXT DEFAULT '{}',
    icpg_state TEXT,
    node_summary TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fatigue_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_utilization REAL DEFAULT 0.0,
    scope_scatter REAL DEFAULT 0.0,
    reread_ratio REAL DEFAULT 0.0,
    error_density REAL DEFAULT 0.0,
    composite_score REAL DEFAULT 0.0,
    state TEXT DEFAULT 'flow',
    computed_at TEXT NOT NULL
);

-- ============================================================
-- Anti-bloat: two-stage eviction
-- ============================================================

CREATE TABLE IF NOT EXISTS pending_eviction (
    node_id TEXT PRIMARY KEY,
    node_table TEXT NOT NULL,
    reason TEXT,
    scheduled_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- ============================================================
-- Schema versioning
-- ============================================================

CREATE TABLE IF NOT EXISTS _migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);

-- ============================================================
-- Full-text search (unicode61 tokenizer for code identifiers)
-- ============================================================

CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
    file_path,
    content,
    language,
    tokenize='unicode61'
);
"""

INDEXES_DDL = """
CREATE INDEX IF NOT EXISTS idx_file_index_project ON file_index(project_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);
CREATE INDEX IF NOT EXISTS idx_symbols_lang ON symbols(language);
CREATE INDEX IF NOT EXISTS idx_symbols_line ON symbols(file_path, line_start);
CREATE INDEX IF NOT EXISTS idx_symbols_pinned ON symbols(is_pinned) WHERE is_pinned = 1;
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_layer ON edges(layer);
CREATE INDEX IF NOT EXISTS idx_edges_from_type ON edges(from_type);
CREATE INDEX IF NOT EXISTS idx_edges_to_type ON edges(to_type);
CREATE INDEX IF NOT EXISTS idx_reasons_status ON reasons(status);
CREATE INDEX IF NOT EXISTS idx_reasons_pinned ON reasons(is_pinned) WHERE is_pinned = 1;
CREATE INDEX IF NOT EXISTS idx_drift_symbol ON drift_events(symbol_id);
CREATE INDEX IF NOT EXISTS idx_drift_resolved ON drift_events(resolved);
CREATE INDEX IF NOT EXISTS idx_mnemo_task ON mnemo_nodes(task_id);
CREATE INDEX IF NOT EXISTS idx_mnemo_type ON mnemo_nodes(type);
CREATE INDEX IF NOT EXISTS idx_mnemo_status ON mnemo_nodes(status);
CREATE INDEX IF NOT EXISTS idx_mnemo_pinned ON mnemo_nodes(is_pinned) WHERE is_pinned = 1;
CREATE INDEX IF NOT EXISTS idx_checkpoints_task ON checkpoints(task_id);
CREATE INDEX IF NOT EXISTS idx_pending_eviction_expires ON pending_eviction(expires_at);
"""
