"""Memory layer core logic — _memory_impl, _checkpoint_impl, _fatigue_impl."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.db import CortexDB

EVICTION_THRESHOLD = 0.05
PROTECTED_TYPES = {'goal', 'constraint', 'checkpoint', 'handoff'}
COMPRESS_TYPES = {'observation', 'result', 'decision', 'context'}


async def _memory_impl(
    db: CortexDB,
    action: str = 'add',
    node_type: str | None = None,
    task_id: str | None = None,
    content: str | None = None,
    scope_tags: str | None = None,
    min_weight: float | None = None,
) -> str:
    match action:
        case 'add':
            return await _memory_add(
                db, node_type, task_id, content, scope_tags,
            )
        case 'query':
            return await _memory_query(
                db, node_type, task_id, min_weight,
            )
        case 'consolidate':
            return await _memory_consolidate(db)
        case _:
            return json.dumps(
                {'error': f'Unknown action: {action}'},
            )


async def _memory_add(
    db: CortexDB,
    node_type: str | None,
    task_id: str | None,
    content: str | None,
    scope_tags: str | None,
) -> str:
    if not node_type or not task_id or not content:
        return json.dumps(
            {'error': 'node_type, task_id, content required'},
        )
    new_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    tags = [
        t.strip() for t in (scope_tags or '').split(',')
        if t.strip()
    ]
    await db.write(
        'INSERT INTO mnemo_nodes '
        '(id, type, task_id, content, '
        'activation_weight, status, scope_tags, '
        'created_at, last_accessed) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (new_id, node_type, task_id, content, 1.0,
         'active', json.dumps(tags), now, now),
    )
    return json.dumps({
        'id': new_id, 'type': node_type,
        'task_id': task_id, 'status': 'active',
    })


async def _memory_query(
    db: CortexDB,
    node_type: str | None,
    task_id: str | None,
    min_weight: float | None,
) -> str:
    conditions: list[str] = ['status = ?']
    params: list[Any] = ['active']
    if node_type:
        conditions.append('type = ?')
        params.append(node_type)
    if task_id:
        conditions.append('task_id = ?')
        params.append(task_id)
    if min_weight is not None:
        conditions.append('activation_weight >= ?')
        params.append(min_weight)
    where = ' AND '.join(conditions)
    params.append(50)
    rows = await db.read(
        f'SELECT id, type, task_id, content, summary, '
        f'activation_weight, status, scope_tags, '
        f'created_at, last_accessed, access_count '
        f'FROM mnemo_nodes WHERE {where} '
        f'ORDER BY activation_weight DESC LIMIT ?',
        tuple(params),
    )
    return json.dumps([
        {
            'id': r[0], 'type': r[1], 'task_id': r[2],
            'content': r[3][:200], 'summary': r[4],
            'activation_weight': r[5], 'status': r[6],
            'scope_tags': json.loads(r[7]) if r[7] else [],
            'created_at': r[8], 'last_accessed': r[9],
            'access_count': r[10],
        }
        for r in rows
    ])


async def _memory_consolidate(db: CortexDB) -> str:
    now = datetime.now(timezone.utc).isoformat()
    rows = await db.read(
        'SELECT id, type, is_pinned, content '
        'FROM mnemo_nodes '
        'WHERE activation_weight < ? AND status = ?',
        (EVICTION_THRESHOLD, 'active'),
    )
    skipped = 0
    compressed = 0
    evicted = 0
    for r in rows:
        nid, ntype, pinned, ncontent = r[0], r[1], r[2], r[3]
        if pinned or ntype in PROTECTED_TYPES:
            skipped += 1
            continue
        if ntype in COMPRESS_TYPES:
            await db.write(
                'UPDATE mnemo_nodes '
                'SET summary = ?, status = ? WHERE id = ?',
                (ncontent[:200], 'compressed', nid),
            )
            compressed += 1
        else:
            await db.write(
                'INSERT INTO pending_eviction '
                '(node_id, node_table, reason, '
                'scheduled_at, expires_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (nid, 'mnemo_nodes',
                 'low activation weight', now, now),
            )
            await db.write(
                'UPDATE mnemo_nodes SET status = ? '
                'WHERE id = ?',
                ('pending_eviction', nid),
            )
            evicted += 1
    return json.dumps({
        'processed': len(rows),
        'skipped': skipped,
        'compressed': compressed,
        'evicted': evicted,
    })


async def _checkpoint_impl(
    db: CortexDB,
    action: str = 'write',
    task_id: str | None = None,
    goal: str | None = None,
    project_dir: Path | None = None,
) -> str:
    match action:
        case 'write':
            return await _checkpoint_write(
                db, task_id, goal, project_dir,
            )
        case 'resume':
            return await _checkpoint_resume(db, task_id)
        case _:
            return json.dumps(
                {'error': f'Unknown action: {action}'},
            )


async def _checkpoint_write(
    db: CortexDB,
    task_id: str | None,
    goal: str | None,
    project_dir: Path | None,
) -> str:
    if not task_id or not goal:
        return json.dumps(
            {'error': 'task_id and goal required'},
        )
    import asyncio

    new_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    goal_nodes = await db.read(
        'SELECT content FROM mnemo_nodes '
        'WHERE type = ? AND task_id = ? AND status = ?',
        ('goal', task_id, 'active'),
    )
    goals_content = [r[0] for r in goal_nodes]

    constraint_nodes = await db.read(
        'SELECT content FROM mnemo_nodes '
        'WHERE type = ? AND task_id = ? AND status = ?',
        ('constraint', task_id, 'active'),
    )
    constraints = [r[0] for r in constraint_nodes]

    result_nodes = await db.read(
        'SELECT content FROM mnemo_nodes '
        'WHERE type = ? AND task_id = ? AND status = ?',
        ('result', task_id, 'active'),
    )
    results = [r[0] for r in result_nodes]

    git_state = await _get_git_state(project_dir)

    fatigue_rows = await db.read(
        'SELECT composite_score, state FROM fatigue_log '
        'ORDER BY computed_at DESC LIMIT 1', (),
    )
    fatigue_score = fatigue_rows[0][0] if fatigue_rows else 0.0

    await db.write(
        'INSERT INTO checkpoints '
        '(id, task_id, goal, active_constraints, '
        'active_results, working_memory, git_state, '
        'fatigue_at_checkpoint, node_summary, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (new_id, task_id, goal,
         json.dumps(constraints), json.dumps(results),
         json.dumps(goals_content), json.dumps(git_state),
         fatigue_score,
         json.dumps({
             'goals': len(goals_content),
             'constraints': len(constraints),
             'results': len(results),
         }), now),
    )
    return json.dumps({
        'id': new_id, 'task_id': task_id,
        'goal': goal, 'created_at': now,
    })


async def _checkpoint_resume(
    db: CortexDB, task_id: str | None,
) -> str:
    if task_id:
        rows = await db.read(
            'SELECT id, task_id, goal, '
            'active_constraints, active_results, '
            'working_memory, git_state, '
            'fatigue_at_checkpoint, node_summary, '
            'created_at '
            'FROM checkpoints WHERE task_id = ? '
            'ORDER BY created_at DESC LIMIT 1',
            (task_id,),
        )
    else:
        rows = await db.read(
            'SELECT id, task_id, goal, '
            'active_constraints, active_results, '
            'working_memory, git_state, '
            'fatigue_at_checkpoint, node_summary, '
            'created_at '
            'FROM checkpoints '
            'ORDER BY created_at DESC LIMIT 1', (),
        )
    if not rows:
        return json.dumps({'error': 'No checkpoint found'})
    r = rows[0]
    return json.dumps({
        'id': r[0], 'task_id': r[1], 'goal': r[2],
        'constraints': json.loads(r[3]) if r[3] else [],
        'results': json.loads(r[4]) if r[4] else [],
        'working_memory': json.loads(r[5]) if r[5] else [],
        'git_state': json.loads(r[6]) if r[6] else {},
        'fatigue_at_checkpoint': r[7],
        'node_summary': json.loads(r[8]) if r[8] else {},
        'created_at': r[9],
    })


async def _get_git_state(
    project_dir: Path | None,
) -> dict[str, str]:
    if project_dir is None:
        return {}
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            'git', 'rev-parse', '--abbrev-ref', 'HEAD',
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        branch = out.decode().strip()
        proc2 = await asyncio.create_subprocess_exec(
            'git', 'status', '--porcelain',
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out2, _ = await proc2.communicate()
        return {
            'branch': branch,
            'status': out2.decode().strip(),
        }
    except (OSError, FileNotFoundError):
        return {'error': 'git not available'}


async def _fatigue_impl(db: CortexDB) -> str:
    rows = await db.read(
        'SELECT token_utilization, scope_scatter, '
        'reread_ratio, error_density, composite_score, '
        'state, computed_at '
        'FROM fatigue_log '
        'ORDER BY computed_at DESC LIMIT 1', (),
    )
    if not rows:
        return json.dumps({
            'token_utilization': 0.0,
            'scope_scatter': 0.0,
            'reread_ratio': 0.0,
            'error_density': 0.0,
            'composite_score': 0.0,
            'state': 'flow',
        })
    r = rows[0]
    return json.dumps({
        'token_utilization': r[0], 'scope_scatter': r[1],
        'reread_ratio': r[2], 'error_density': r[3],
        'composite_score': r[4], 'state': r[5],
        'computed_at': r[6],
    })
