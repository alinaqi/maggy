"""Cross-layer MCP tool registrations — cortex_explain, cortex_status."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import Context


def _get_db(ctx: Context) -> Any:
    return ctx.request_context['db']


def register(cortex: Any) -> None:
    @cortex.tool(
        name='cortex_explain',
        description=(
            'Full cross-layer context for any symbol/file. '
            'Returns structure + intent + memory.'
        ),
    )
    async def cortex_explain(
        target: str,
        ctx: Context = None,
    ) -> str:
        db = _get_db(ctx)
        symbols = await db.read(
            'SELECT id, name, file_path, symbol_type, '
            'language, signature, line_start, line_end, '
            'docstring FROM symbols WHERE name = ?',
            (target,),
        )
        if not symbols:
            symbols = await db.read(
                'SELECT id, name, file_path, symbol_type, '
                'language, signature, line_start, line_end, '
                'docstring FROM symbols '
                'WHERE file_path LIKE ?',
                (f'%{target}%',),
            )
        structure = await _build_structure(db, symbols)
        intent = await _build_intent(db, symbols)
        memory = await _build_memory(db, symbols)
        return json.dumps({
            'target': target,
            'structure': structure,
            'intent': intent,
            'memory': memory,
        }, indent=2)

    @cortex.tool(
        name='cortex_status',
        description=(
            'Unified dashboard: index health, drift, '
            'fatigue, recommendations'
        ),
    )
    async def cortex_status(ctx: Context = None) -> str:
        db = _get_db(ctx)
        counts = await _gather_counts(db)
        fatigue = await _get_fatigue(db)
        recs = _build_recommendations(counts, fatigue)
        return json.dumps({
            **counts,
            'fatigue': fatigue,
            'recommendations': recs,
        }, indent=2)


async def _build_structure(
    db: Any, symbols: list,
) -> list[dict[str, Any]]:
    result = []
    for s in symbols:
        callers = await db.read(
            'SELECT s2.name FROM edges e '
            'JOIN symbols s2 ON e.from_id = s2.id '
            'WHERE e.to_id = ? AND e.edge_type = ?',
            (s[0], 'CALLS'),
        )
        callees = await db.read(
            'SELECT s2.name FROM edges e '
            'JOIN symbols s2 ON e.to_id = s2.id '
            'WHERE e.from_id = ? AND e.edge_type = ?',
            (s[0], 'CALLS'),
        )
        result.append({
            'name': s[1], 'file': s[2], 'type': s[3],
            'language': s[4], 'signature': s[5],
            'line_start': s[6], 'line_end': s[7],
            'docstring': s[8],
            'called_by': [r[0] for r in callers],
            'calls': [r[0] for r in callees],
        })
    return result


async def _build_intent(
    db: Any, symbols: list,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for s in symbols:
        reasons = await db.read(
            'SELECT r.id, r.goal, r.owner, r.status, '
            'r.decision_type FROM reasons r '
            'JOIN edges e ON e.from_id = r.id '
            'WHERE e.to_id = ? '
            'AND e.edge_type IN (?, ?)',
            (s[0], 'CREATES', 'MODIFIES'),
        )
        for r in reasons:
            drift = await db.read(
                'SELECT id, severity, description, resolved '
                'FROM drift_events '
                'WHERE symbol_id = ? AND from_reason_id = ?',
                (s[0], r[0]),
            )
            result.append({
                'reason_id': r[0], 'goal': r[1],
                'owner': r[2], 'status': r[3], 'type': r[4],
                'drift': [
                    {
                        'severity': d[1],
                        'description': d[2],
                        'resolved': bool(d[3]),
                    }
                    for d in drift
                ],
            })
    return result


async def _build_memory(
    db: Any, symbols: list,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for s in symbols:
        nodes = await db.read(
            'SELECT type, content, status, last_accessed, '
            'access_count FROM mnemo_nodes '
            'WHERE content LIKE ? AND status = ? LIMIT 5',
            (f'%{s[1]}%', 'active'),
        )
        result.extend([
            {
                'type': n[0], 'content': n[1][:200],
                'status': n[2], 'last_accessed': n[3],
                'access_count': n[4],
            }
            for n in nodes
        ])
    return result


async def _gather_counts(db: Any) -> dict[str, Any]:
    projects = await db.read(
        'SELECT COUNT(*) FROM projects', (),
    )
    symbols = await db.read(
        'SELECT COUNT(*) FROM symbols', (),
    )
    edges = await db.read(
        'SELECT COUNT(*) FROM edges', (),
    )
    reasons = await db.read(
        'SELECT COUNT(*) FROM reasons', (),
    )
    drift = await db.read(
        'SELECT COUNT(*) FROM drift_events '
        'WHERE resolved = 0', (),
    )
    mnemo = await db.read(
        'SELECT COUNT(*) FROM mnemo_nodes '
        'WHERE status = ?', ('active',),
    )
    checkpoints = await db.read(
        'SELECT COUNT(*) FROM checkpoints', (),
    )
    pending = await db.read(
        'SELECT COUNT(*) FROM pending_eviction', (),
    )
    return {
        'projects': projects[0][0],
        'symbols': symbols[0][0],
        'edges': edges[0][0],
        'reasons': reasons[0][0],
        'unresolved_drift': drift[0][0],
        'active_memory_nodes': mnemo[0][0],
        'checkpoints': checkpoints[0][0],
        'pending_eviction': pending[0][0],
    }


async def _get_fatigue(db: Any) -> dict[str, Any]:
    rows = await db.read(
        'SELECT composite_score, state FROM fatigue_log '
        'ORDER BY computed_at DESC LIMIT 1', (),
    )
    return {
        'score': rows[0][0] if rows else 0.0,
        'state': rows[0][1] if rows else 'flow',
    }


def _build_recommendations(
    counts: dict[str, Any],
    fatigue: dict[str, Any],
) -> list[str]:
    recs = []
    if counts['symbols'] == 0:
        recs.append('Run cortex_index to index your project')
    if counts['unresolved_drift'] > 0:
        recs.append(
            f'{counts["unresolved_drift"]} unresolved drift '
            'events — run cortex_analyze',
        )
    if fatigue['score'] > 0.6:
        recs.append(
            'High fatigue — consider cortex_checkpoint '
            'to save progress',
        )
    if counts['pending_eviction'] > 0:
        recs.append(
            f'{counts["pending_eviction"]} nodes pending '
            'eviction',
        )
    return recs
