"""Tests for the idempotent session-hooks installer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from install_session_hooks import install, main

STOP_HOOK = {
    'type': 'command',
    'command': 'exec mnemos-stop-ingest.sh',
    'timeout': 10,
    'statusMessage': 'Ingesting...',
}


def _source(tmp: Path, hooks: dict, allow: list | None = None) -> Path:
    data: dict = {'hooks': hooks}
    if allow is not None:
        data['permissions'] = {'allow': allow}
    p = tmp / 'source.json'
    p.write_text(json.dumps(data))
    return p


def _read_target(project: Path) -> dict:
    return json.loads((project / '.claude' / 'settings.json').read_text())


def test_creates_settings_and_installs_hook(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    project.mkdir()
    src = _source(tmp_path, {'Stop': [{'hooks': [STOP_HOOK]}]})

    result = install(project, src)

    assert result['ok'] and result['hooks_added'] == 1
    target = _read_target(project)
    cmds = [h['command'] for g in target['hooks']['Stop'] for h in g['hooks']]
    assert 'exec mnemos-stop-ingest.sh' in cmds


def test_is_idempotent(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    project.mkdir()
    src = _source(tmp_path, {'Stop': [{'hooks': [STOP_HOOK]}]})

    install(project, src)
    second = install(project, src)

    assert second['hooks_added'] == 0
    target = _read_target(project)
    stop_entries = [h for g in target['hooks']['Stop'] for h in g['hooks']]
    assert len(stop_entries) == 1  # no duplicate


def test_preserves_existing_project_hooks(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    (project / '.claude').mkdir(parents=True)
    custom = {'type': 'command', 'command': 'my-custom-hook.sh'}
    (project / '.claude' / 'settings.json').write_text(
        json.dumps({'hooks': {'Stop': [{'hooks': [custom]}]}})
    )
    src = _source(tmp_path, {'Stop': [{'hooks': [STOP_HOOK]}]})

    install(project, src)

    cmds = [h['command']
            for g in _read_target(project)['hooks']['Stop']
            for h in g['hooks']]
    assert 'my-custom-hook.sh' in cmds
    assert 'exec mnemos-stop-ingest.sh' in cmds


def test_merges_permission_allows_deduped(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    (project / '.claude').mkdir(parents=True)
    (project / '.claude' / 'settings.json').write_text(
        json.dumps({'permissions': {'allow': ['Bash(ls *)']}})
    )
    src = _source(tmp_path, {'Stop': [{'hooks': [STOP_HOOK]}]},
                  allow=['Bash(ls *)', 'Bash(mnemos *)'])

    result = install(project, src)

    allow = _read_target(project)['permissions']['allow']
    assert allow.count('Bash(ls *)') == 1  # not duplicated
    assert 'Bash(mnemos *)' in allow
    assert result['allow_added'] == 1


def test_respects_matcher_grouping(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    project.mkdir()
    src = _source(tmp_path, {'PreToolUse': [
        {'matcher': 'Edit', 'hooks': [{'type': 'command', 'command': 'a.sh'}]},
    ]})
    # pre-existing different matcher must be kept separate
    (project / '.claude').mkdir(parents=True)
    (project / '.claude' / 'settings.json').write_text(json.dumps(
        {'hooks': {'PreToolUse': [
            {'matcher': 'Write', 'hooks': [{'type': 'command', 'command': 'b.sh'}]},
        ]}}
    ))

    install(project, src)

    groups = _read_target(project)['hooks']['PreToolUse']
    matchers = {g.get('matcher') for g in groups}
    assert matchers == {'Edit', 'Write'}


def test_missing_source_returns_error(tmp_path: Path) -> None:
    project = tmp_path / 'proj'
    project.mkdir()
    rc = main(['--project', str(project),
               '--source', str(tmp_path / 'does-not-exist.json')])
    assert rc == 1
