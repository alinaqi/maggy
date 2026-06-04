"""Unit tests for mnemos.haziness scoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from mnemos.claude_log import ingest_session
from mnemos.haziness import WEIGHTS, band, compute_haze, dominant_dim
from mnemos.store import MnemosStore


SESSION_ID = '22222222-2222-2222-2222-222222222222'


def _write(path: Path, events: list[dict]) -> None:
    with path.open('w', encoding='utf-8') as f:
        for ev in events:
            f.write(json.dumps(ev) + '\n')


def _u(text: str, cwd: str, uid: str) -> dict:
    return {
        'type': 'user', 'sessionId': SESSION_ID,
        'uuid': uid, 'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
        'message': {'role': 'user', 'content': text},
    }


def _assist_text(text: str, cwd: str, uid: str) -> dict:
    return {
        'type': 'assistant', 'sessionId': SESSION_ID,
        'uuid': uid, 'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
        'message': {'role': 'assistant', 'model': 'm',
                    'content': [{'type': 'text', 'text': text}]},
    }


def _assist_tool(tool: str, input_: dict, cwd: str,
                 uid: str, tool_id: str) -> dict:
    return {
        'type': 'assistant', 'sessionId': SESSION_ID,
        'uuid': uid, 'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
        'message': {'role': 'assistant', 'model': 'm',
                    'content': [{'type': 'tool_use', 'id': tool_id,
                                 'name': tool, 'input': input_}]},
    }


def _tool_result(tool_id: str, content: str, cwd: str,
                 is_error: bool = False) -> dict:
    return {
        'type': 'user', 'sessionId': SESSION_ID,
        'uuid': f'tr-{tool_id}', 'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
        'message': {'role': 'user', 'content': [{
            'type': 'tool_result', 'tool_use_id': tool_id,
            'content': content, 'is_error': is_error,
        }]},
    }


@pytest.fixture
def store(tmp_path: Path) -> MnemosStore:
    d = tmp_path / 'p'
    d.mkdir()
    s = MnemosStore(str(d))
    s.init_db()
    return s


@pytest.fixture
def mktranscript(tmp_path: Path):
    def _mk(events: list[dict]) -> Path:
        slug = tmp_path / '-home-demo'
        slug.mkdir(exist_ok=True)
        p = slug / f'{SESSION_ID}.jsonl'
        _write(p, events)
        return p
    return _mk


def _ingest(store, mktranscript, events) -> dict:
    path = mktranscript(events)
    ingest_session(store, path)
    return compute_haze(store, SESSION_ID)


def test_empty_session_zero_composite(store):
    # No turns exist for this session id.
    result = compute_haze(store, SESSION_ID)
    assert result['composite'] == 0.0
    assert result['turns_analyzed'] == 0
    for dim in WEIGHTS:
        assert result[dim] == 0.0


def test_composite_bounded_0_1(store, mktranscript):
    cwd = '/home/demo'
    result = _ingest(store, mktranscript, [
        _u('no, wrong', cwd, 'u1'),
        _assist_tool('Edit', {'file_path': '/a.py'}, cwd, 'a1', 't1'),
        _tool_result('t1', 'Error: bad', cwd, is_error=True),
    ])
    assert 0.0 <= result['composite'] <= 1.0


def test_correction_density_dominant(store, mktranscript):
    cwd = '/home/demo'
    events = []
    for i in range(5):
        events.append(_u(f'no, wrong step {i}', cwd, f'u{i}'))
        events.append(_assist_text(f'ok trying again {i}', cwd, f'a{i}'))
    result = _ingest(store, mktranscript, events)
    assert result['correction_density'] > 0.9
    assert dominant_dim(result) == 'correction_density'


def test_first_try_error_rate_dominant(store, mktranscript):
    cwd = '/home/demo'
    events = []
    for i in range(4):
        tool_id = f't{i}'
        events.append(_assist_tool(
            'Edit', {'file_path': f'/f{i}.py'}, cwd, f'a{i}', tool_id,
        ))
        events.append(_tool_result(
            tool_id, 'Error: broken', cwd, is_error=True,
        ))
        events.append(_u(f'ok continue {i}', cwd, f'u{i}'))
    result = _ingest(store, mktranscript, events)
    assert result['first_try_error_rate'] == 1.0


def test_redo_ratio_dominant(store, mktranscript):
    cwd = '/home/demo'
    # Edit same file, get error, edit same file again -- should count as redo.
    events = []
    for i in range(4):
        events.append(_assist_tool(
            'Edit', {'file_path': '/same.py'}, cwd, f'a{i}a', f'fst{i}',
        ))
        events.append(_tool_result(
            f'fst{i}', 'Error', cwd, is_error=True,
        ))
        events.append(_assist_tool(
            'Edit', {'file_path': '/same.py'}, cwd, f'a{i}b', f'snd{i}',
        ))
        events.append(_tool_result(f'snd{i}', 'ok', cwd))
    result = _ingest(store, mktranscript, events)
    assert result['redo_ratio'] > 0.0


def test_orphan_tool_use_dominant(store, mktranscript):
    cwd = '/home/demo'
    # Every tool_use lacks a matching tool_result -> orphan rate 1.0.
    events = []
    for i in range(3):
        events.append(_assist_tool(
            'Read', {'file_path': f'/x{i}.py'}, cwd, f'a{i}', f'orphan{i}',
        ))
    result = _ingest(store, mktranscript, events)
    assert result['orphan_tool_use_rate'] == 1.0


def test_backtrack_norm(store, mktranscript):
    cwd = '/home/demo'
    events = []
    for i in range(5):
        events.append({
            'type': 'assistant', 'sessionId': SESSION_ID,
            'uuid': f'b{i}', 'parentUuid': None,
            'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
            'message': {'role': 'assistant', 'model': 'm',
                        'content': [{'type': 'tool_use', 'id': f'bt{i}',
                                     'name': 'Bash',
                                     'input': {'command': 'git revert HEAD~1'}}]}
        })
    result = _ingest(store, mktranscript, events)
    assert result['backtrack_norm'] == 1.0


def test_backtrack_ignores_non_backtrack_git(store, mktranscript):
    cwd = '/home/demo'
    events = [{
        'type': 'assistant', 'sessionId': SESSION_ID,
        'uuid': 'b0', 'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z', 'cwd': cwd,
        'message': {'role': 'assistant', 'model': 'm',
                    'content': [{'type': 'tool_use', 'id': 'bt0',
                                 'name': 'Bash',
                                 'input': {'command': 'git checkout --orphan main'}}]}
    }]
    result = _ingest(store, mktranscript, events)
    assert result['backtrack_norm'] == 0.0


def test_band_thresholds():
    assert band(0.0) == 'clear'
    assert band(0.24) == 'clear'
    assert band(0.25) == 'cloudy'
    assert band(0.49) == 'cloudy'
    assert band(0.50) == 'hazy'
    assert band(0.74) == 'hazy'
    assert band(0.75) == 'lost'
    assert band(1.0) == 'lost'


def test_recompute_updates_existing_row(store, mktranscript):
    cwd = '/home/demo'
    path = mktranscript([_u('hi', cwd, 'u1')])
    ingest_session(store, path)
    r1 = compute_haze(store, SESSION_ID)
    r2 = compute_haze(store, SESSION_ID)
    assert r1['composite'] == r2['composite']
    # Only one row in claude_haze.
    with store._conn() as conn:
        count = conn.execute(
            'SELECT COUNT(*) AS c FROM claude_haze WHERE session_id = ?',
            (SESSION_ID,),
        ).fetchone()['c']
        assert count == 1
