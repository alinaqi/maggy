"""Graph traversal engine — BFS/DFS via recursive CTEs on SQLite edges."""

from __future__ import annotations

from typing import Any

from .db import CortexDB, Row

type TraceResult = dict[str, Any]


async def trace_path(
    db: CortexDB,
    from_symbol: str,
    mode: str = 'calls',
    max_depth: int = 10,
    to_symbol: str | None = None,
    direction: str = 'out',
) -> list[TraceResult]:
    edge_types = _mode_to_edge_types(mode)
    placeholders = ','.join('?' for _ in edge_types)

    if direction == 'in':
        edge_join = 'JOIN edges e ON t.id = e.to_id'
        sym_join = 'JOIN symbols s2 ON e.from_id = s2.id'
    elif direction == 'both':
        edge_join = 'JOIN edges e ON (t.id = e.from_id OR t.id = e.to_id)'
        sym_join = (
            'JOIN symbols s2 ON s2.id = '
            'CASE WHEN t.id = e.from_id THEN e.to_id '
            'ELSE e.from_id END'
        )
    else:
        edge_join = 'JOIN edges e ON t.id = e.from_id'
        sym_join = 'JOIN symbols s2 ON e.to_id = s2.id'

    sql = f"""
    WITH RECURSIVE traverse(id, name, file_path, edge_type, depth, path) AS (
        SELECT s.id, s.name, s.file_path, NULL, 0, s.name
        FROM symbols s WHERE s.name = ?
        UNION ALL
        SELECT s2.id, s2.name, s2.file_path, e.edge_type,
               t.depth + 1, t.path || ' -> ' || s2.name
        FROM traverse t
        {edge_join}
        {sym_join}
        WHERE t.depth < ?
          AND e.edge_type IN ({placeholders})
          AND instr(t.path, s2.name) = 0
    )
    SELECT DISTINCT id, name, file_path, edge_type, depth, path
    FROM traverse
    ORDER BY depth
    """
    params: tuple[Any, ...] = (from_symbol, max_depth, *edge_types)
    rows = await db.read(sql, params)

    results = [
        {
            'id': r[0],
            'name': r[1],
            'file_path': r[2],
            'edge_type': r[3],
            'depth': r[4],
            'path': r[5],
        }
        for r in rows
    ]

    if to_symbol:
        results = [r for r in results if r['name'] == to_symbol]

    return results


async def get_neighbors(
    db: CortexDB,
    symbol_id: str,
    direction: str = 'out',
    edge_types: list[str] | None = None,
    max_depth: int = 1,
) -> list[Row]:
    if direction == 'out':
        join_col, target_col = 'from_id', 'to_id'
    else:
        join_col, target_col = 'to_id', 'from_id'

    type_filter = ''
    params: list[Any] = [symbol_id, max_depth]
    if edge_types:
        placeholders = ','.join('?' for _ in edge_types)
        type_filter = f'AND e.edge_type IN ({placeholders})'
        params.extend(edge_types)

    sql = f"""
    WITH RECURSIVE neighbors(id, depth) AS (
        VALUES (?, 0)
        UNION ALL
        SELECT e.{target_col}, n.depth + 1
        FROM neighbors n
        JOIN edges e ON n.id = e.{join_col}
        WHERE n.depth < ? {type_filter}
    )
    SELECT DISTINCT s.id, s.name, s.file_path, s.symbol_type, s.language, n.depth
    FROM neighbors n
    JOIN symbols s ON n.id = s.id
    WHERE n.depth > 0
    ORDER BY n.depth
    """
    return await db.read(sql, tuple(params))


async def get_blast_radius(
    db: CortexDB,
    symbol_id: str,
    max_depth: int = 5,
) -> dict[str, Any]:
    callers = await get_neighbors(
        db, symbol_id, direction='in',
        edge_types=['CALLS', 'IMPORTS'], max_depth=max_depth,
    )
    callees = await get_neighbors(
        db, symbol_id, direction='out',
        edge_types=['CALLS', 'IMPORTS'], max_depth=max_depth,
    )
    return {
        'symbol_id': symbol_id,
        'callers': len(callers),
        'callees': len(callees),
        'total_affected': len(callers) + len(callees),
        'caller_details': [
            {'name': r[1], 'file': r[2], 'depth': r[5]} for r in callers
        ],
        'callee_details': [
            {'name': r[1], 'file': r[2], 'depth': r[5]} for r in callees
        ],
    }


def _mode_to_edge_types(mode: str) -> list[str]:
    match mode:
        case 'calls':
            return ['CALLS', 'IMPORTS']
        case 'data_flow':
            return ['READS', 'WRITES', 'RETURNS']
        case 'cross_service':
            return ['CALLS', 'IMPORTS', 'HTTP_CALLS']
        case _:
            return ['CALLS', 'IMPORTS']
