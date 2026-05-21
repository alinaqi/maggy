"""Tests for cross-layer tools — cortex_explain and cortex_status.

Tests verify that the WOW features correctly aggregate data
from Structure, Intent, and Memory layers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.storage.db import CortexDB
from cortex.tools.unified_tools import (
    _build_intent,
    _build_memory,
    _build_structure,
    _gather_counts,
    _get_fatigue,
    _build_recommendations,
)


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


NOW = '2026-01-01T00:00:00Z'


async def _seed_full(db: CortexDB) -> None:
    await db.write(
        'INSERT INTO symbols '
        '(id, name, file_path, symbol_type, language, '
        'checksum, line_start, line_end, docstring, '
        'created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        ('sym-1', 'validateToken', '/proj/auth.py',
         'function', 'python', 'abc', 10, 25,
         'Validate JWT token', NOW),
    )
    await db.write(
        'INSERT INTO reasons '
        '(id, goal, owner, scope, status, '
        'decision_type, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        ('r-1', 'Implement JWT auth', 'alice',
         '[]', 'fulfilled', 'task', NOW),
    )
    await db.write(
        'INSERT INTO edges '
        '(id, from_id, from_type, to_id, to_type, '
        'edge_type, layer, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ('e-1', 'r-1', 'reason', 'sym-1', 'symbol',
         'CREATES', 'intent', NOW),
    )
    await db.write(
        'INSERT INTO mnemo_nodes '
        '(id, type, task_id, content, '
        'activation_weight, status, is_pinned, '
        'created_at, last_accessed, access_count) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        ('m-1', 'observation', 'task-1',
         'Found bug in validateToken parsing',
         1.0, 'active', 0, NOW, NOW, 3),
    )


class TestBuildStructure:
    async def test_returns_symbol_info(
        self, db: CortexDB,
    ) -> None:
        await _seed_full(db)
        symbols = await db.read(
            'SELECT id, name, file_path, symbol_type, '
            'language, signature, line_start, line_end, '
            'docstring FROM symbols WHERE name = ?',
            ('validateToken',),
        )
        result = await _build_structure(db, symbols)
        assert len(result) == 1
        assert result[0]['name'] == 'validateToken'
        assert result[0]['file'] == '/proj/auth.py'
        assert result[0]['type'] == 'function'

    async def test_empty_symbols(self, db: CortexDB) -> None:
        result = await _build_structure(db, [])
        assert result == []


class TestBuildIntent:
    async def test_returns_linked_reasons(
        self, db: CortexDB,
    ) -> None:
        await _seed_full(db)
        symbols = await db.read(
            'SELECT id, name, file_path, symbol_type, '
            'language, signature, line_start, line_end, '
            'docstring FROM symbols WHERE name = ?',
            ('validateToken',),
        )
        result = await _build_intent(db, symbols)
        assert len(result) == 1
        assert result[0]['goal'] == 'Implement JWT auth'
        assert result[0]['owner'] == 'alice'

    async def test_includes_drift_events(
        self, db: CortexDB,
    ) -> None:
        await _seed_full(db)
        await db.write(
            'INSERT INTO drift_events '
            '(id, symbol_id, from_reason_id, severity, '
            'description, resolved, detected_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('d-1', 'sym-1', 'r-1', 0.8,
             'checksum changed', 0, NOW),
        )
        symbols = await db.read(
            'SELECT id, name, file_path, symbol_type, '
            'language, signature, line_start, line_end, '
            'docstring FROM symbols WHERE name = ?',
            ('validateToken',),
        )
        result = await _build_intent(db, symbols)
        assert len(result[0]['drift']) == 1
        assert result[0]['drift'][0]['severity'] == 0.8


class TestBuildMemory:
    async def test_returns_related_nodes(
        self, db: CortexDB,
    ) -> None:
        await _seed_full(db)
        symbols = await db.read(
            'SELECT id, name, file_path, symbol_type, '
            'language, signature, line_start, line_end, '
            'docstring FROM symbols WHERE name = ?',
            ('validateToken',),
        )
        result = await _build_memory(db, symbols)
        assert len(result) == 1
        assert 'validateToken' in result[0]['content']


class TestGatherCounts:
    async def test_returns_zero_counts_when_empty(
        self, db: CortexDB,
    ) -> None:
        result = await _gather_counts(db)
        assert result['projects'] == 0
        assert result['symbols'] == 0
        assert result['edges'] == 0

    async def test_returns_correct_counts(
        self, db: CortexDB,
    ) -> None:
        await _seed_full(db)
        result = await _gather_counts(db)
        assert result['symbols'] == 1
        assert result['edges'] == 1
        assert result['reasons'] == 1
        assert result['active_memory_nodes'] == 1


class TestGetFatigue:
    async def test_defaults_when_empty(
        self, db: CortexDB,
    ) -> None:
        result = await _get_fatigue(db)
        assert result['score'] == 0.0
        assert result['state'] == 'flow'

    async def test_returns_latest(
        self, db: CortexDB,
    ) -> None:
        await db.write(
            'INSERT INTO fatigue_log '
            '(token_utilization, scope_scatter, '
            'reread_ratio, error_density, '
            'composite_score, state, computed_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (0.9, 0.7, 0.5, 0.3, 0.75, 'fatigued', NOW),
        )
        result = await _get_fatigue(db)
        assert result['score'] == 0.75
        assert result['state'] == 'fatigued'


class TestBuildRecommendations:
    def test_recommends_index_when_empty(self) -> None:
        counts = {
            'symbols': 0, 'unresolved_drift': 0,
            'pending_eviction': 0,
        }
        recs = _build_recommendations(
            counts, {'score': 0.0, 'state': 'flow'},
        )
        assert any('cortex_index' in r for r in recs)

    def test_recommends_analyze_on_drift(self) -> None:
        counts = {
            'symbols': 10, 'unresolved_drift': 3,
            'pending_eviction': 0,
        }
        recs = _build_recommendations(
            counts, {'score': 0.0, 'state': 'flow'},
        )
        assert any('cortex_analyze' in r for r in recs)

    def test_recommends_checkpoint_on_fatigue(self) -> None:
        counts = {
            'symbols': 10, 'unresolved_drift': 0,
            'pending_eviction': 0,
        }
        recs = _build_recommendations(
            counts, {'score': 0.8, 'state': 'fatigued'},
        )
        assert any('cortex_checkpoint' in r for r in recs)

    def test_no_recommendations_when_healthy(self) -> None:
        counts = {
            'symbols': 10, 'unresolved_drift': 0,
            'pending_eviction': 0,
        }
        recs = _build_recommendations(
            counts, {'score': 0.2, 'state': 'flow'},
        )
        assert len(recs) == 0
