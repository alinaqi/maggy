"""Tests for intent and memory tools — cortex_intent, cortex_analyze,
cortex_bootstrap, cortex_contracts, cortex_memory, cortex_checkpoint,
cortex_fatigue.

Tests call the _*_impl core functions directly (bypassing FastMCP
decorator which disallows underscore params).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.storage.db import CortexDB


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


async def _seed_symbol(
    db: CortexDB,
    sym_id: str = 'sym-1',
    name: str = 'main',
    file_path: str = '/proj/src/main.py',
) -> None:
    await db.write(
        'INSERT INTO symbols '
        '(id, name, file_path, symbol_type, language, '
        'checksum, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (sym_id, name, file_path, 'function', 'python',
         'abc123', '2026-01-01T00:00:00Z'),
    )


# ── Intent tools ──────────────────────────────────────────────


class TestCortexIntentCreate:
    async def test_create_returns_id_and_goal(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        await _seed_symbol(db)

        result = json.loads(await _intent_impl(
            db,
            action='create',
            goal='Add entry point for CLI',
            scope='/proj/src/main.py',
            owner='alice',
            decision_type='task',
        ))
        assert 'id' in result
        assert result['goal'] == 'Add entry point for CLI'
        assert result['status'] == 'proposed'

    async def test_create_inserts_reason_row(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        await _seed_symbol(db)

        result = json.loads(await _intent_impl(
            db,
            action='create',
            goal='Wire up auth',
            scope='/proj/src/main.py',
            owner='bob',
        ))
        rows = await db.read(
            'SELECT id, goal, owner FROM reasons WHERE id = ?',
            (result['id'],),
        )
        assert len(rows) == 1
        assert rows[0][1] == 'Wire up auth'

    async def test_create_links_edges_to_matching_symbols(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        await _seed_symbol(db)

        result = json.loads(await _intent_impl(
            db,
            action='create',
            goal='Refactor main',
            scope='/proj/src/main.py',
            owner='carol',
        ))
        edges = await db.read(
            'SELECT from_id, to_id, edge_type FROM edges '
            'WHERE from_id = ? AND edge_type = ?',
            (result['id'], 'CREATES'),
        )
        assert len(edges) >= 1
        assert edges[0][1] == 'sym-1'


class TestCortexIntentQuery:
    async def test_query_returns_linked_reasons(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        await _seed_symbol(db)

        await _intent_impl(
            db,
            action='create',
            goal='Add logging',
            scope='/proj/src/main.py',
            owner='dave',
        )
        result = json.loads(await _intent_impl(
            db,
            action='query',
            file_path='/proj/src/main.py',
        ))
        assert len(result) >= 1
        assert result[0]['goal'] == 'Add logging'

    async def test_query_empty_file_returns_empty(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        result = json.loads(await _intent_impl(
            db,
            action='query',
            file_path='/nonexistent/file.py',
        ))
        assert result == []


class TestCortexIntentPriorWork:
    async def test_prior_work_finds_similar_goals(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _intent_impl
        await _seed_symbol(db)

        await _intent_impl(
            db,
            action='create',
            goal='Implement JWT authentication',
            scope='/proj/src/main.py',
            owner='eve',
        )
        result = json.loads(await _intent_impl(
            db,
            action='prior_work',
            goal='authentication',
        ))
        assert len(result) >= 1
        assert 'JWT' in result[0]['goal']


# ── Analyze tools ─────────────────────────────────────────────


class TestCortexAnalyzeRisk:
    async def test_risk_returns_counts(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _analyze_impl
        await _seed_symbol(db)

        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO reasons '
            '(id, goal, owner, scope, created_at) '
            'VALUES (?, ?, ?, ?, ?)',
            ('r-1', 'Add feature', 'alice', '[]', now),
        )
        await db.write(
            'INSERT INTO edges '
            '(id, from_id, from_type, to_id, to_type, '
            'edge_type, layer, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('e-1', 'r-1', 'reason', 'sym-1', 'symbol',
             'MODIFIES', 'intent', now),
        )
        await db.write(
            'INSERT INTO drift_events '
            '(id, symbol_id, from_reason_id, severity, '
            'description, resolved, detected_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('d-1', 'sym-1', 'r-1', 0.7,
             'checksum changed', 0, now),
        )

        result = json.loads(await _analyze_impl(
            db,
            mode='risk',
            symbol_name='main',
        ))
        assert result['modification_count'] >= 1
        assert result['active_drift_events'] >= 1


class TestCortexAnalyzeBlastRadius:
    async def test_blast_radius_delegates_to_graph(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _analyze_impl
        await _seed_symbol(db)

        result = json.loads(await _analyze_impl(
            db,
            mode='blast_radius',
            symbol_name='main',
        ))
        assert 'symbol_id' in result
        assert 'total_affected' in result


# ── Contracts ─────────────────────────────────────────────────


class TestCortexContracts:
    async def test_returns_contracts_for_symbol(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _contracts_impl
        await _seed_symbol(db)

        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO reasons '
            '(id, goal, owner, scope, preconditions, '
            'postconditions, invariants, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('r-1', 'Add auth', 'alice', '[]',
             json.dumps(['token must be valid']),
             json.dumps(['user is authenticated']),
             json.dumps(['session must exist']),
             now),
        )
        await db.write(
            'INSERT INTO edges '
            '(id, from_id, from_type, to_id, to_type, '
            'edge_type, layer, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('e-1', 'r-1', 'reason', 'sym-1', 'symbol',
             'CREATES', 'intent', now),
        )

        result = json.loads(await _contracts_impl(
            db, symbol_name='main',
        ))
        assert len(result) >= 1
        assert result[0]['preconditions'] == [
            'token must be valid',
        ]
        assert result[0]['postconditions'] == [
            'user is authenticated',
        ]
        assert result[0]['invariants'] == [
            'session must exist',
        ]


# ── Memory tools ──────────────────────────────────────────────


class TestCortexMemoryAdd:
    async def test_add_returns_node_id(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        result = json.loads(await _memory_impl(
            db,
            action='add',
            node_type='observation',
            task_id='task-1',
            content='Found a bug in auth module',
            scope_tags='auth,bug',
        ))
        assert 'id' in result
        assert result['type'] == 'observation'

    async def test_add_inserts_row(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        result = json.loads(await _memory_impl(
            db,
            action='add',
            node_type='observation',
            task_id='task-1',
            content='Memory content here',
        ))
        rows = await db.read(
            'SELECT id, content FROM mnemo_nodes '
            'WHERE id = ?',
            (result['id'],),
        )
        assert len(rows) == 1
        assert rows[0][1] == 'Memory content here'


class TestCortexMemoryQuery:
    async def test_query_filters_by_type(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        await _memory_impl(
            db,
            action='add',
            node_type='observation',
            task_id='task-1',
            content='Observation 1',
        )
        await _memory_impl(
            db,
            action='add',
            node_type='goal',
            task_id='task-1',
            content='Goal 1',
        )
        result = json.loads(await _memory_impl(
            db,
            action='query',
            node_type='goal',
            task_id='task-1',
        ))
        assert len(result) == 1
        assert result[0]['type'] == 'goal'

    async def test_query_all_returns_active(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        await _memory_impl(
            db,
            action='add',
            node_type='observation',
            task_id='task-1',
            content='Active node',
        )
        result = json.loads(await _memory_impl(
            db,
            action='query',
            task_id='task-1',
        ))
        assert len(result) >= 1


class TestCortexMemoryConsolidate:
    async def test_consolidate_skips_pinned(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO mnemo_nodes '
            '(id, type, task_id, content, '
            'activation_weight, status, is_pinned, '
            'created_at, last_accessed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('m-pin', 'observation', 'task-1',
             'Pinned node', 0.01, 'active', 1, now, now),
        )
        result = json.loads(await _memory_impl(
            db, action='consolidate',
        ))
        assert result['skipped'] >= 1
        rows = await db.read(
            'SELECT status FROM mnemo_nodes WHERE id = ?',
            ('m-pin',),
        )
        assert rows[0][0] == 'active'

    async def test_consolidate_compresses_eligible(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        now = '2026-01-01T00:00:00Z'
        long_content = 'A' * 500
        await db.write(
            'INSERT INTO mnemo_nodes '
            '(id, type, task_id, content, '
            'activation_weight, status, is_pinned, '
            'created_at, last_accessed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('m-comp', 'observation', 'task-1',
             long_content, 0.01, 'active', 0, now, now),
        )
        result = json.loads(await _memory_impl(
            db, action='consolidate',
        ))
        assert result['compressed'] >= 1
        rows = await db.read(
            'SELECT status, summary FROM mnemo_nodes '
            'WHERE id = ?',
            ('m-comp',),
        )
        assert rows[0][0] == 'compressed'
        assert len(rows[0][1]) <= 200

    async def test_consolidate_evicts_non_compressible(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _memory_impl
        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO mnemo_nodes '
            '(id, type, task_id, content, '
            'activation_weight, status, is_pinned, '
            'created_at, last_accessed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('m-evict', 'trace', 'task-1', 'Trace data',
             0.01, 'active', 0, now, now),
        )
        result = json.loads(await _memory_impl(
            db, action='consolidate',
        ))
        assert result['evicted'] >= 1
        evicted = await db.read(
            'SELECT node_id FROM pending_eviction '
            'WHERE node_id = ?',
            ('m-evict',),
        )
        assert len(evicted) == 1


# ── Checkpoint ────────────────────────────────────────────────


class TestCortexCheckpoint:
    async def test_write_creates_checkpoint(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _checkpoint_impl
        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO mnemo_nodes '
            '(id, type, task_id, content, '
            'activation_weight, status, is_pinned, '
            'created_at, last_accessed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('m-goal', 'goal', 'task-1',
             'Ship auth feature', 1.0, 'active',
             0, now, now),
        )

        result = json.loads(await _checkpoint_impl(
            db,
            action='write',
            task_id='task-1',
            goal='Complete authentication',
            project_dir=None,
        ))
        assert 'id' in result
        assert result['task_id'] == 'task-1'

    async def test_resume_loads_latest(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _checkpoint_impl
        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO mnemo_nodes '
            '(id, type, task_id, content, '
            'activation_weight, status, is_pinned, '
            'created_at, last_accessed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('m-goal', 'goal', 'task-1',
             'Ship auth feature', 1.0, 'active',
             0, now, now),
        )

        await _checkpoint_impl(
            db,
            action='write',
            task_id='task-1',
            goal='Complete auth',
            project_dir=None,
        )

        result = json.loads(await _checkpoint_impl(
            db,
            action='resume',
            task_id='task-1',
        ))
        assert result['task_id'] == 'task-1'
        assert result['goal'] == 'Complete auth'

    async def test_resume_not_found(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _checkpoint_impl
        result = json.loads(await _checkpoint_impl(
            db,
            action='resume',
            task_id='nonexistent',
        ))
        assert 'error' in result


# ── Fatigue ───────────────────────────────────────────────────


class TestCortexFatigue:
    async def test_returns_defaults_when_empty(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _fatigue_impl
        result = json.loads(await _fatigue_impl(db))
        assert result['composite_score'] == 0.0
        assert result['state'] == 'flow'

    async def test_returns_latest_entry(
        self, db: CortexDB
    ) -> None:
        from cortex.server import _fatigue_impl
        now = '2026-01-01T00:00:00Z'
        await db.write(
            'INSERT INTO fatigue_log '
            '(token_utilization, scope_scatter, '
            'reread_ratio, error_density, '
            'composite_score, state, computed_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (0.8, 0.5, 0.3, 0.2, 0.65, 'fatigued', now),
        )
        result = json.loads(await _fatigue_impl(db))
        assert result['composite_score'] == 0.65
        assert result['state'] == 'fatigued'
