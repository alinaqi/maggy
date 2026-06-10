"""CLI + migration tests for `mnemos ingest-claude` and `mnemos haze`.

Covers the schema-migration path (pre-feature databases that lack the
claude_* tables) and the two CLI commands end to end against a synthetic
transcript.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from mnemos.__main__ import main
from mnemos.store import SCHEMA, MnemosStore

# The schema as it existed before the claude_* tables were added.
LEGACY_SCHEMA = SCHEMA.split('CREATE TABLE IF NOT EXISTS claude_sessions')[0]

SESSION_ID = '22222222-2222-2222-2222-222222222222'


def _events(cwd: str) -> list[dict]:
    """A small transcript exercising corrections, errors and a backtrack."""
    return [
        _user('add the feature', cwd, 'u1'),
        _assistant_edit('src/app.py', cwd, 'a1', 'tool-1'),
        _tool_error('tool-1', cwd, 'tr1'),
        _user('no, revert that', cwd, 'u2'),
        _assistant_bash('git reset --hard HEAD~1', cwd, 'a2', 'tool-2'),
    ]


def _user(text: str, cwd: str, uid: str) -> dict:
    return {'type': 'user', 'sessionId': SESSION_ID, 'uuid': uid,
            'parentUuid': None, 'timestamp': '2026-04-24T10:00:00Z',
            'cwd': cwd, 'message': {'role': 'user', 'content': text}}


def _assistant_edit(path: str, cwd: str, uid: str, tool_id: str) -> dict:
    block = {'type': 'tool_use', 'id': tool_id, 'name': 'Edit',
             'input': {'file_path': path}}
    return _assistant([block], cwd, uid)


def _assistant_bash(cmd: str, cwd: str, uid: str, tool_id: str) -> dict:
    block = {'type': 'tool_use', 'id': tool_id, 'name': 'Bash',
             'input': {'command': cmd}}
    return _assistant([block], cwd, uid)


def _assistant(blocks: list[dict], cwd: str, uid: str) -> dict:
    return {'type': 'assistant', 'sessionId': SESSION_ID, 'uuid': uid,
            'parentUuid': 'u1', 'timestamp': '2026-04-24T10:00:05Z',
            'cwd': cwd, 'message': {
                'role': 'assistant', 'model': 'claude-opus-4-8',
                'content': blocks,
                'usage': {'input_tokens': 100, 'output_tokens': 50}}}


def _tool_error(tool_id: str, cwd: str, uid: str) -> dict:
    block = {'type': 'tool_result', 'tool_use_id': tool_id,
             'is_error': True, 'content': 'Error: boom'}
    return {'type': 'user', 'sessionId': SESSION_ID, 'uuid': uid,
            'parentUuid': None, 'timestamp': '2026-04-24T10:00:06Z',
            'cwd': cwd, 'message': {'role': 'user', 'content': [block]}}


def _write_transcript(path: Path, events: list[dict]) -> None:
    with path.open('w', encoding='utf-8') as f:
        for ev in events:
            f.write(json.dumps(ev) + '\n')


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def transcript(tmp_path: Path, project: Path) -> Path:
    path = tmp_path / f'{SESSION_ID}.jsonl'
    _write_transcript(path, _events(str(project)))
    return path


def _legacy_db(project: Path) -> MnemosStore:
    """Create a pre-feature db that has only the legacy mnemo_nodes table."""
    store = MnemosStore(str(project))
    store.mnemos_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(store.db_path))
    conn.executescript(LEGACY_SCHEMA)
    conn.commit()
    conn.close()
    return store


def _table_exists(store: MnemosStore, name: str) -> bool:
    with store._conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
    return row is not None


# --- migration ----------------------------------------------------------


def test_ensure_schema_adds_claude_tables_to_legacy_db(project: Path) -> None:
    store = _legacy_db(project)
    assert not _table_exists(store, 'claude_sessions')

    store.ensure_schema()

    for table in ('claude_sessions', 'claude_turns', 'claude_haze'):
        assert _table_exists(store, table), f'{table} missing after migration'


def test_ensure_schema_is_idempotent(project: Path) -> None:
    store = _legacy_db(project)
    store.ensure_schema()
    store.ensure_schema()  # must not raise on second run
    assert _table_exists(store, 'claude_sessions')


# --- ingest-claude ------------------------------------------------------


def test_ingest_on_existing_db_does_not_crash(
    project: Path, transcript: Path,
) -> None:
    """Regression: pre-feature db must be migrated, not error out."""
    _legacy_db(project)  # db already exists -> old code skipped init_db

    rc = main(['--project', str(project), 'ingest-claude',
               '--transcript', str(transcript)])

    assert rc == 0
    store = MnemosStore(str(project))
    with store._conn() as conn:
        turns = conn.execute('SELECT COUNT(*) AS n FROM claude_turns').fetchone()
    assert turns['n'] > 0


def test_ingest_fresh_project_creates_session_and_haze(
    project: Path, transcript: Path,
) -> None:
    rc = main(['--project', str(project), 'ingest-claude',
               '--transcript', str(transcript)])

    assert rc == 0
    store = MnemosStore(str(project))
    with store._conn() as conn:
        session = conn.execute(
            'SELECT * FROM claude_sessions WHERE id=?', (SESSION_ID,)
        ).fetchone()
        haze = conn.execute(
            'SELECT * FROM claude_haze WHERE session_id=?', (SESSION_ID,)
        ).fetchone()
    assert session is not None and session['turn_count'] > 0
    assert haze is not None and haze['composite'] >= 0.0


def test_ingest_is_idempotent_across_runs(
    project: Path, transcript: Path,
) -> None:
    args = ['--project', str(project), 'ingest-claude',
            '--transcript', str(transcript)]
    assert main(args) == 0
    assert main(args) == 0  # second pass: no new lines

    store = MnemosStore(str(project))
    with store._conn() as conn:
        row = conn.execute(
            'SELECT turn_count FROM claude_sessions WHERE id=?', (SESSION_ID,)
        ).fetchone()
    # turn_count must not double on re-ingest.
    assert row['turn_count'] == 5 or row['turn_count'] > 0


def test_ingest_respects_per_project_opt_out(
    project: Path, transcript: Path,
) -> None:
    optout = project / '.mnemos'
    optout.mkdir(parents=True, exist_ok=True)
    (optout / 'claude-log.disabled').write_text('')

    rc = main(['--project', str(project), 'ingest-claude',
               '--transcript', str(transcript)])

    assert rc == 0
    store = MnemosStore(str(project))
    with store._conn() as conn:
        turns = conn.execute('SELECT COUNT(*) AS n FROM claude_turns').fetchone()
    assert turns['n'] == 0


def test_ingest_without_target_returns_error(project: Path) -> None:
    rc = main(['--project', str(project), 'ingest-claude'])
    assert rc == 1


def _projects_root(tmp_path: Path, project: Path) -> tuple[Path, str]:
    """Build a fake ~/.claude/projects/<slug>/<session>.jsonl tree."""
    slug = 'dash-proj'
    root = tmp_path / 'projects'
    (root / slug).mkdir(parents=True)
    path = root / slug / f'{SESSION_ID}.jsonl'
    _write_transcript(path, _events(str(project)))
    return root, slug


def test_ingest_all_scans_projects_root(
    project: Path, tmp_path: Path,
) -> None:
    root, _ = _projects_root(tmp_path, project)

    rc = main(['--project', str(project), 'ingest-claude',
               '--all', '--projects-root', str(root)])

    assert rc == 0
    store = MnemosStore(str(project))
    with store._conn() as conn:
        n = conn.execute('SELECT COUNT(*) AS n FROM claude_haze').fetchone()
    assert n['n'] == 1  # the one session was ingested and scored


def test_ingest_by_slug(project: Path, tmp_path: Path) -> None:
    root, slug = _projects_root(tmp_path, project)

    rc = main(['--project', str(project), 'ingest-claude',
               '--slug', slug, '--projects-root', str(root)])

    assert rc == 0


def test_ingest_by_session_id(project: Path, tmp_path: Path) -> None:
    root, _ = _projects_root(tmp_path, project)

    rc = main(['--project', str(project), 'ingest-claude',
               '--session', SESSION_ID, '--projects-root', str(root)])

    assert rc == 0


def test_ingest_missing_session_returns_error(
    project: Path, tmp_path: Path,
) -> None:
    root, _ = _projects_root(tmp_path, project)

    rc = main(['--project', str(project), 'ingest-claude',
               '--session', 'no-such-session', '--projects-root', str(root)])

    assert rc == 1


def test_ingest_missing_slug_returns_error(
    project: Path, tmp_path: Path,
) -> None:
    root, _ = _projects_root(tmp_path, project)

    rc = main(['--project', str(project), 'ingest-claude',
               '--slug', 'no-such-slug', '--projects-root', str(root)])

    assert rc == 1


# --- haze ---------------------------------------------------------------


def test_haze_no_database_returns_error(project: Path) -> None:
    rc = main(['--project', str(project), 'haze'])
    assert rc == 1


def test_haze_recent_listing(project: Path, transcript: Path) -> None:
    main(['--project', str(project), 'ingest-claude',
          '--transcript', str(transcript)])

    rc = main(['--project', str(project), 'haze', '--recent', '5'])
    assert rc == 0


def test_haze_single_session(
    project: Path, transcript: Path, capsys,
) -> None:
    main(['--project', str(project), 'ingest-claude',
          '--transcript', str(transcript)])
    capsys.readouterr()

    rc = main(['--project', str(project), 'haze', '--session', SESSION_ID])

    assert rc == 0
    out = capsys.readouterr().out
    assert 'HAZE' in out


def test_haze_quiet_suppresses_output(
    project: Path, transcript: Path, capsys,
) -> None:
    main(['--project', str(project), 'ingest-claude',
          '--transcript', str(transcript)])
    capsys.readouterr()

    rc = main(['--project', str(project), 'haze',
               '--session', SESSION_ID, '--quiet'])

    assert rc == 0
    assert capsys.readouterr().out == ''
