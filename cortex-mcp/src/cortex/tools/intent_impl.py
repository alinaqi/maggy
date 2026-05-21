"""Intent layer core logic — _intent_impl, _analyze_impl, _bootstrap_impl, _contracts_impl."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.db import CortexDB


async def _intent_impl(
    db: CortexDB,
    action: str = 'create',
    goal: str | None = None,
    scope: str | None = None,
    owner: str | None = None,
    decision_type: str = 'task',
    file_path: str | None = None,
) -> str:
    match action:
        case 'create':
            return await _intent_create(
                db, goal, scope, owner, decision_type,
            )
        case 'query':
            return await _intent_query(db, file_path)
        case 'prior_work':
            return await _intent_prior_work(db, goal)
        case _:
            return json.dumps({'error': f'Unknown action: {action}'})


async def _intent_create(
    db: CortexDB,
    goal: str | None,
    scope: str | None,
    owner: str | None,
    decision_type: str,
) -> str:
    if not goal or not owner:
        return json.dumps({'error': 'goal and owner required'})
    new_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    scope_list = [
        s.strip() for s in (scope or '').split(',') if s.strip()
    ]
    await db.write(
        'INSERT INTO reasons '
        '(id, goal, decision_type, scope, owner, '
        'status, source, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (new_id, goal, decision_type,
         json.dumps(scope_list), owner,
         'proposed', 'manual', now),
    )
    for scope_path in scope_list:
        symbols = await db.read(
            'SELECT id FROM symbols WHERE file_path = ?',
            (scope_path,),
        )
        for sym in symbols:
            edge_id = str(uuid.uuid4())[:8]
            await db.write(
                'INSERT INTO edges '
                '(id, from_id, from_type, to_id, to_type, '
                'edge_type, layer, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (edge_id, new_id, 'reason', sym[0],
                 'symbol', 'CREATES', 'intent', now),
            )
    return json.dumps({
        'id': new_id, 'goal': goal,
        'status': 'proposed', 'scope': scope_list,
    })


async def _intent_query(
    db: CortexDB, file_path: str | None,
) -> str:
    if not file_path:
        return json.dumps({'error': 'file_path required'})
    rows = await db.read(
        'SELECT DISTINCT r.id, r.goal, r.owner, '
        'r.status, r.decision_type, r.scope '
        'FROM reasons r '
        'JOIN edges e ON e.from_id = r.id '
        'JOIN symbols s ON e.to_id = s.id '
        'WHERE s.file_path = ? '
        'AND e.edge_type IN (?, ?)',
        (file_path, 'CREATES', 'MODIFIES'),
    )
    return json.dumps([
        {
            'id': r[0], 'goal': r[1], 'owner': r[2],
            'status': r[3], 'type': r[4],
            'scope': json.loads(r[5]) if r[5] else [],
        }
        for r in rows
    ])


async def _intent_prior_work(
    db: CortexDB, goal: str | None,
) -> str:
    if not goal:
        return json.dumps({'error': 'goal required'})
    rows = await db.read(
        'SELECT id, goal, scope, owner, status '
        'FROM reasons WHERE goal LIKE ?',
        (f'%{goal}%',),
    )
    return json.dumps([
        {
            'id': r[0], 'goal': r[1],
            'scope': json.loads(r[2]) if r[2] else [],
            'owner': r[3], 'status': r[4],
        }
        for r in rows
    ])


async def _analyze_impl(
    db: CortexDB,
    mode: str = 'drift',
    file_path: str | None = None,
    symbol_name: str | None = None,
    max_depth: int = 5,
) -> str:
    match mode:
        case 'drift':
            return await _analyze_drift(db, file_path)
        case 'risk':
            return await _analyze_risk(db, symbol_name)
        case 'blast_radius':
            return await _analyze_blast(
                db, symbol_name, max_depth,
            )
        case _:
            return json.dumps({'error': f'Unknown mode: {mode}'})


async def _analyze_drift(
    db: CortexDB, file_path: str | None,
) -> str:
    if file_path:
        symbols = await db.read(
            'SELECT s.id, s.name, s.checksum, r.id, r.goal '
            'FROM symbols s '
            'JOIN edges e ON e.to_id = s.id '
            'JOIN reasons r ON e.from_id = r.id '
            'WHERE s.file_path = ? '
            'AND e.edge_type IN (?, ?)',
            (file_path, 'CREATES', 'MODIFIES'),
        )
    else:
        symbols = await db.read(
            'SELECT s.id, s.name, s.checksum, r.id, r.goal '
            'FROM symbols s '
            'JOIN edges e ON e.to_id = s.id '
            'JOIN reasons r ON e.from_id = r.id '
            'WHERE e.edge_type IN (?, ?)',
            ('CREATES', 'MODIFIES'),
        )
    drift_list: list[dict[str, Any]] = []
    for s in symbols:
        existing = await db.read(
            'SELECT id FROM drift_events '
            'WHERE symbol_id = ? AND from_reason_id = ? '
            'AND resolved = 0',
            (s[0], s[3]),
        )
        if existing:
            drift_list.append({
                'symbol': s[1], 'reason_id': s[3],
                'goal': s[4], 'status': 'drifted',
            })
    return json.dumps(drift_list)


async def _analyze_risk(
    db: CortexDB, symbol_name: str | None,
) -> str:
    if not symbol_name:
        return json.dumps({'error': 'symbol_name required'})
    sym_rows = await db.read(
        'SELECT id FROM symbols WHERE name = ?',
        (symbol_name,),
    )
    if not sym_rows:
        return json.dumps(
            {'error': f'Symbol not found: {symbol_name}'},
        )
    sym_id = sym_rows[0][0]
    mod_count = await db.read(
        'SELECT COUNT(*) FROM edges '
        'WHERE to_id = ? AND edge_type = ?',
        (sym_id, 'MODIFIES'),
    )
    owner_count = await db.read(
        'SELECT COUNT(DISTINCT r.owner) FROM reasons r '
        'JOIN edges e ON e.from_id = r.id '
        'WHERE e.to_id = ? AND e.edge_type IN (?, ?)',
        (sym_id, 'CREATES', 'MODIFIES'),
    )
    drift_count = await db.read(
        'SELECT COUNT(*) FROM drift_events '
        'WHERE symbol_id = ? AND resolved = 0',
        (sym_id,),
    )
    return json.dumps({
        'symbol': symbol_name, 'symbol_id': sym_id,
        'modification_count': mod_count[0][0],
        'distinct_owners': owner_count[0][0],
        'active_drift_events': drift_count[0][0],
    })


async def _analyze_blast(
    db: CortexDB,
    symbol_name: str | None,
    max_depth: int,
) -> str:
    if not symbol_name:
        return json.dumps({'error': 'symbol_name required'})
    sym_rows = await db.read(
        'SELECT id FROM symbols WHERE name = ?',
        (symbol_name,),
    )
    if not sym_rows:
        return json.dumps(
            {'error': f'Symbol not found: {symbol_name}'},
        )
    from ..storage.graph import get_blast_radius
    return json.dumps(
        await get_blast_radius(db, sym_rows[0][0], max_depth),
    )


async def _bootstrap_impl(
    db: CortexDB,
    project_dir: Path,
    commit_count: int = 50,
) -> str:
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        'git', 'log', '--oneline', f'-{commit_count}',
        cwd=str(project_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = [
        ln for ln in stdout.decode().strip().split('\n') if ln
    ]

    created = 0
    now = datetime.now(timezone.utc).isoformat()
    for line in lines:
        parts = line.split(' ', 1)
        if len(parts) < 2:
            continue
        commit_hash, message = parts
        new_id = str(uuid.uuid4())[:8]
        await db.write(
            'INSERT INTO reasons '
            '(id, goal, decision_type, scope, owner, '
            'status, source, task_id, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id, message.strip(), 'commit', '[]',
             'git', 'fulfilled', 'commit',
             commit_hash, now),
        )
        created += 1

    return json.dumps({
        'commits_parsed': len(lines),
        'reasons_created': created,
    })


async def _contracts_impl(
    db: CortexDB,
    symbol_name: str,
) -> str:
    rows = await db.read(
        'SELECT r.id, r.goal, r.preconditions, '
        'r.postconditions, r.invariants, r.owner '
        'FROM reasons r '
        'JOIN edges e ON e.from_id = r.id '
        'JOIN symbols s ON e.to_id = s.id '
        'WHERE s.name = ? AND e.edge_type IN (?, ?)',
        (symbol_name, 'CREATES', 'MODIFIES'),
    )
    return json.dumps([
        {
            'reason_id': r[0], 'goal': r[1],
            'preconditions': json.loads(r[2]) if r[2] else [],
            'postconditions': json.loads(r[3]) if r[3] else [],
            'invariants': json.loads(r[4]) if r[4] else [],
            'owner': r[5],
        }
        for r in rows
    ])
