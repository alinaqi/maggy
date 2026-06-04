"""Idempotently install claude-bootstrap session hooks into a project.

Merges the canonical `hooks` (and additive permission `allow` entries) from a
source settings.json — normally the installed template at
`~/.claude/templates/settings.json` — into a project's `.claude/settings.json`.

Non-destructive: existing project hooks/permissions are preserved and hook
entries are de-duplicated by command, so re-running is safe (idempotent).
The hook commands themselves resolve their scripts from `.claude/scripts/`
with a `$HOME/.claude/templates/` fallback, so no scripts are copied here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _default_source() -> Path:
    return Path.home() / '.claude' / 'templates' / 'settings.json'


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _group_key(group: dict) -> str:
    return group.get('matcher', '')


def _commands(group: dict) -> set[str]:
    return {h.get('command', '') for h in group.get('hooks', [])}


def merge_event(target_groups: list, source_groups: list) -> int:
    """Merge one event's hook groups. Returns count of entries added."""
    added = 0
    for s_group in source_groups:
        match = next((g for g in target_groups
                      if _group_key(g) == _group_key(s_group)), None)
        if match is None:
            target_groups.append(json.loads(json.dumps(s_group)))
            added += len(s_group.get('hooks', []))
            continue
        existing = _commands(match)
        for entry in s_group.get('hooks', []):
            if entry.get('command', '') not in existing:
                match.setdefault('hooks', []).append(entry)
                added += 1
    return added


def merge_hooks(target: dict, source_hooks: dict) -> int:
    hooks = target.setdefault('hooks', {})
    added = 0
    for event, groups in source_hooks.items():
        added += merge_event(hooks.setdefault(event, []), groups)
    return added


def merge_allow(target: dict, source_allow: list) -> int:
    allow = target.setdefault('permissions', {}).setdefault('allow', [])
    added = 0
    for item in source_allow:
        if item not in allow:
            allow.append(item)
            added += 1
    return added


def install(project_dir: Path, source: Path) -> dict:
    src = load_json(source)
    if not src.get('hooks'):
        return {'ok': False, 'reason': 'no hooks in source',
                'source': str(source)}
    target_path = project_dir / '.claude' / 'settings.json'
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target = load_json(target_path)
    hooks_added = merge_hooks(target, src['hooks'])
    allow_added = merge_allow(
        target, src.get('permissions', {}).get('allow', []))
    target_path.write_text(json.dumps(target, indent=2) + '\n')
    return {'ok': True, 'hooks_added': hooks_added,
            'allow_added': allow_added, 'target': str(target_path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='install-session-hooks')
    ap.add_argument('--project', default='.', help='Project dir (default: .)')
    ap.add_argument('--source', help='Source settings.json '
                    '(default: ~/.claude/templates/settings.json)')
    args = ap.parse_args(argv)
    source = Path(args.source) if args.source else _default_source()
    result = install(Path(args.project), source)
    if not result['ok']:
        print(f"No hooks installed: {result['reason']} "
              f"({result.get('source')})")
        return 1
    print(f"Session hooks installed -> {result['target']} "
          f"(+{result['hooks_added']} hooks, "
          f"+{result['allow_added']} permissions)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
