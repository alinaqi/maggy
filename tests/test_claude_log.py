"""Unit tests for mnemos.claude_log ingester."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from mnemos.claude_log import ingest_session
from mnemos.store import MnemosStore


SESSION_ID = '11111111-1111-1111-1111-111111111111'


def _write_transcript(path: Path, events: list[dict]) -> None:
    with path.open('w', encoding='utf-8') as f:
        for ev in events:
            f.write(json.dumps(ev) + '\n')


def _user_event(text: str, cwd: str) -> dict:
    return {
        'type': 'user',
        'sessionId': SESSION_ID,
        'uuid': f'uu-{hash(text) & 0xFFFF:x}',
        'parentUuid': None,
        'timestamp': '2026-04-24T10:00:00Z',
        'cwd': cwd,
        'message': {'role': 'user', 'content': text},
    }


def _assistant_event(
    blocks: list[dict], cwd: str, uid: str = 'aa-1',
) -> dict:
    return {
        'type': 'assistant',
        'sessionId': SESSION_ID,
        'uuid': uid,
        'parentUuid': 'uu-parent',
        'timestamp': '2026-04-24T10:00:05Z',
        'cwd': cwd,
        'message': {
            'role': 'assistant',
            'model': 'claude-sonnet-4-6',
            'content': blocks,
            'usage': {'input_tokens': 100, 'output_tokens': 50},
        },
    }


def _tool_result_event(tool_use_id: str, result: str, cwd: str,
                      is_error: bool = False) -> dict:
    return {
        'type': 'user',
        'sessionId': SESSION_ID,
        'uuid': f'tr-{tool_use_id}',
        'parentUuid': None,
        'timestamp': '2026-04-24T10:00:06Z',
        'cwd': cwd,
        'message': {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_use_id': tool_use_id,
                'content': result,
                'is_error': is_error,
            }],
        },
    }


@pytest.fixture
def store(tmp_path: Path) -> MnemosStore:
    project_dir = tmp_path / 'proj'
    project_dir.mkdir()
    s = MnemosStore(str(project_dir))
    s.init_db()
    return s


@pytest.fixture
def transcript_path(tmp_path: Path) -> Path:
    slug_dir = tmp_path / '-Users-admin-demo'
    slug_dir.mkdir()
    return slug_dir / f'{SESSION_ID}.jsonl'


def test_basic_ingest_inserts_rows(store, transcript_path):
    cwd = '/Users/admin/demo'
    events = [
        _user_event('first message', cwd),
        _assistant_event(
            [{'type': 'text', 'text': 'hi'},
             {'type': 'tool_use', 'id': 't1', 'name': 'Read',
              'input': {'file_path': '/Users/admin/demo/a.py'}}],
            cwd,
        ),
        _tool_result_event('t1', 'file contents', cwd),
    ]
    _write_transcript(transcript_path, events)

    result = ingest_session(store, transcript_path)

    assert result['new_session'] is True
    assert result['turns'] > 0

    with store._conn() as conn:
        session = conn.execute(
            'SELECT * FROM claude_sessions WHERE id = ?',
            (SESSION_ID,),
        ).fetchone()
        assert session['project_path'] == cwd
        assert session['tokens_in'] == 100
        assert session['tokens_out'] == 50
        assert session['model'] == 'claude-sonnet-4-6'

        turn_count = conn.execute(
            'SELECT COUNT(*) AS c FROM claude_turns WHERE session_id = ?',
            (SESSION_ID,),
        ).fetchone()['c']
        assert turn_count == result['turns']


def test_reingest_is_idempotent(store, transcript_path):
    cwd = '/Users/admin/demo'
    events = [
        _user_event('hello', cwd),
        _assistant_event([{'type': 'text', 'text': 'hi'}], cwd),
    ]
    _write_transcript(transcript_path, events)

    r1 = ingest_session(store, transcript_path)
    r2 = ingest_session(store, transcript_path)

    assert r1['turns'] > 0
    assert r2['turns'] == 0

    with store._conn() as conn:
        rows = conn.execute(
            'SELECT COUNT(*) AS c FROM claude_turns WHERE session_id = ?',
            (SESSION_ID,),
        ).fetchone()['c']
        assert rows == r1['turns']


def test_append_then_reingest_picks_up_new(store, transcript_path):
    cwd = '/Users/admin/demo'
    first = [_user_event('one', cwd)]
    _write_transcript(transcript_path, first)
    r1 = ingest_session(store, transcript_path)

    # Append more events; re-ingest should see only new lines.
    with transcript_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(_assistant_event(
            [{'type': 'text', 'text': 'reply'}], cwd,
        )) + '\n')

    r2 = ingest_session(store, transcript_path)
    assert r2['turns'] >= 1
    assert r2['new_session'] is False

    with store._conn() as conn:
        rows = conn.execute(
            'SELECT COUNT(*) AS c FROM claude_turns WHERE session_id = ?',
            (SESSION_ID,),
        ).fetchone()['c']
        assert rows == r1['turns'] + r2['turns']


def test_cwd_comes_from_jsonl_not_path(store, tmp_path):
    """project_path must be the JSON event's cwd, not the parent dir name."""
    slug_dir = tmp_path / '-Users-ali-something-wrong'
    slug_dir.mkdir()
    transcript = slug_dir / f'{SESSION_ID}.jsonl'

    real_cwd = '/Users/ali/actual/project'
    _write_transcript(transcript, [_user_event('x', real_cwd)])

    ingest_session(store, transcript)

    with store._conn() as conn:
        row = conn.execute(
            'SELECT project_path, project_slug FROM claude_sessions WHERE id = ?',
            (SESSION_ID,),
        ).fetchone()
        assert row['project_path'] == real_cwd
        assert row['project_slug'] == '-Users-ali-something-wrong'


def test_disabled_sentinel_skips_ingest(store, transcript_path, tmp_path):
    cwd = str(tmp_path / 'optout_proj')
    Path(cwd).mkdir()
    (Path(cwd) / '.mnemos').mkdir()
    (Path(cwd) / '.mnemos' / 'claude-log.disabled').write_text('')

    _write_transcript(transcript_path, [_user_event('x', cwd)])

    result = ingest_session(store, transcript_path)
    assert result.get('skipped') is True
    assert result.get('reason') == 'disabled'


def test_redaction_applied_by_default(store, transcript_path):
    cwd = '/Users/admin/demo'
    secret = 'sk-ant-abcdef0123456789abcdef0123456789abcdef0123abc'
    _write_transcript(transcript_path, [
        _user_event(f'my key is {secret}', cwd),
    ])

    ingest_session(store, transcript_path)

    with store._conn() as conn:
        row = conn.execute(
            """SELECT text_preview FROM claude_turns
               WHERE session_id = ? AND text_preview IS NOT NULL""",
            (SESSION_ID,),
        ).fetchone()
        assert row is not None
        assert secret not in row['text_preview']
        assert '[REDACTED:anthropic_key]' in row['text_preview']


def test_correction_match_flagged_on_user_turns(store, transcript_path):
    cwd = '/Users/admin/demo'
    _write_transcript(transcript_path, [
        _user_event('no, that is wrong', cwd),
        _user_event('please continue with the next step', cwd),
    ])

    ingest_session(store, transcript_path)

    with store._conn() as conn:
        rows = conn.execute(
            """SELECT text_preview, correction_match FROM claude_turns
               WHERE session_id = ? AND text_preview IS NOT NULL
               ORDER BY idx""",
            (SESSION_ID,),
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]['correction_match'] == 1
        assert rows[1]['correction_match'] == 0


def test_missing_transcript_returns_skipped(store, tmp_path):
    result = ingest_session(store, tmp_path / 'does-not-exist.jsonl')
    assert result.get('skipped') is True
    assert result.get('reason') == 'missing'


def test_bash_command_preview_stored(store, transcript_path):
    cwd = '/Users/admin/demo'
    _write_transcript(transcript_path, [
        _assistant_event(
            [{'type': 'tool_use', 'id': 'b1', 'name': 'Bash',
              'input': {'command': 'git revert HEAD'}}],
            cwd,
        ),
    ])

    ingest_session(store, transcript_path)

    with store._conn() as conn:
        row = conn.execute(
            """SELECT tool_name, text_preview FROM claude_turns
               WHERE session_id = ? AND tool_name = 'Bash'""",
            (SESSION_ID,),
        ).fetchone()
        assert row is not None
        assert 'git revert' in row['text_preview']
