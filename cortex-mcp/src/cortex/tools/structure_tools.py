"""Structure layer MCP tool registrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context


def _get_db(ctx: Context) -> Any:
    return ctx.request_context['db']


def _get_project_dir(ctx: Context) -> Path:
    return ctx.request_context['project_dir']


def register(cortex: Any) -> None:
    @cortex.tool(
        name='cortex_index',
        description=(
            'Index or manage project. '
            'action: "index", "status", "delete", "list"'
        ),
    )
    async def cortex_index(
        action: str = 'index',
        path: str = '.',
        force: bool = False,
        ctx: Context = None,
    ) -> str:
        db = _get_db(ctx)
        project_dir = _get_project_dir(ctx)
        target = (project_dir / path).resolve()
        match action:
            case 'status':
                rows = await db.read(
                    'SELECT file_count, symbol_count, '
                    'last_indexed FROM projects '
                    'WHERE path = ?',
                    (str(target),),
                )
                if not rows:
                    return json.dumps(
                        {'indexed': False, 'path': str(target)},
                    )
                return json.dumps({
                    'indexed': True, 'path': str(target),
                    'files': rows[0][0],
                    'symbols': rows[0][1],
                    'last_indexed': rows[0][2],
                })
            case 'list':
                rows = await db.read(
                    'SELECT path, name, file_count, '
                    'symbol_count, last_indexed '
                    'FROM projects', (),
                )
                return json.dumps([
                    {
                        'path': r[0], 'name': r[1],
                        'files': r[2], 'symbols': r[3],
                        'last_indexed': r[4],
                    }
                    for r in rows
                ])
            case 'delete':
                await db.write(
                    'DELETE FROM symbols '
                    'WHERE file_path LIKE ?',
                    (str(target) + '%',),
                )
                await db.write(
                    'DELETE FROM file_index '
                    'WHERE project_path = ?',
                    (str(target),),
                )
                await db.write(
                    'DELETE FROM projects WHERE path = ?',
                    (str(target),),
                )
                return json.dumps(
                    {'deleted': True, 'path': str(target)},
                )
            case 'index':
                from ..structure.indexer import index_project
                stats = await index_project(
                    db, target, force=force,
                )
                return json.dumps(stats)
            case _:
                return json.dumps(
                    {'error': f'Unknown action: {action}'},
                )

    @cortex.tool(
        name='cortex_search',
        description=(
            'Search symbols or code. '
            'mode: "symbol", "code", "architecture"'
        ),
    )
    async def cortex_search(
        query: str,
        mode: str = 'symbol',
        language: str | None = None,
        symbol_type: str | None = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        db = _get_db(ctx)
        limit = min(limit, 100)
        match mode:
            case 'symbol':
                conditions = ['name LIKE ?']
                params: list[Any] = [f'%{query}%']
                if language:
                    conditions.append('language = ?')
                    params.append(language)
                if symbol_type:
                    conditions.append('symbol_type = ?')
                    params.append(symbol_type)
                params.extend([query, query + '%', limit])
                where = ' AND '.join(conditions)
                rows = await db.read(
                    f'SELECT id, name, file_path, '
                    f'symbol_type, language, signature, '
                    f'line_start, line_end, '
                    f'CASE '
                    f'  WHEN name = ? THEN 0 '
                    f'  WHEN name LIKE ? THEN 1 '
                    f'  ELSE 2 '
                    f'END AS rank '
                    f'FROM symbols WHERE {where} '
                    f'ORDER BY rank, name LIMIT ?',
                    tuple(params),
                )
                return json.dumps([
                    {
                        'id': r[0], 'name': r[1],
                        'file': r[2], 'type': r[3],
                        'language': r[4], 'signature': r[5],
                        'line_start': r[6], 'line_end': r[7],
                    }
                    for r in rows
                ])
            case 'code':
                rows = await db.read(
                    'SELECT file_path, '
                    'snippet(source_fts, 1, ">>", "<<", '
                    '"...", 30), rank '
                    'FROM source_fts '
                    'WHERE content MATCH ? '
                    'ORDER BY rank LIMIT ?',
                    (query, limit),
                )
                return json.dumps([
                    {'file': r[0], 'match': r[1]}
                    for r in rows
                ])
            case 'architecture':
                rows = await db.read(
                    'SELECT file_path, symbol_count, language '
                    'FROM file_index WHERE project_path = '
                    '(SELECT path FROM projects LIMIT 1) '
                    'ORDER BY file_path LIMIT ?',
                    (limit,),
                )
                return json.dumps([
                    {
                        'file': r[0], 'symbols': r[1],
                        'language': r[2],
                    }
                    for r in rows
                ])
            case _:
                return json.dumps(
                    {'error': f'Unknown mode: {mode}'},
                )

    @cortex.tool(
        name='cortex_inspect',
        description=(
            'Inspect a symbol. '
            'mode: "snippet", "schema", "neighbors"'
        ),
    )
    async def cortex_inspect(
        target: str,
        mode: str = 'snippet',
        context_lines: int = 3,
        ctx: Context = None,
    ) -> str:
        db = _get_db(ctx)
        match mode:
            case 'snippet':
                rows = await db.read(
                    'SELECT file_path, line_start, line_end, '
                    'signature, docstring '
                    'FROM symbols WHERE name = ? LIMIT 1',
                    (target,),
                )
                if not rows:
                    return json.dumps(
                        {'error': f'Symbol not found: {target}'},
                    )
                fp, start, end, sig, doc = rows[0]
                if start and end:
                    from ..structure.snippets import (
                        extract_snippet,
                    )
                    snippet = await extract_snippet(
                        Path(fp), start, end, context_lines,
                    )
                else:
                    snippet = sig or ''
                return json.dumps({
                    'name': target, 'file': fp,
                    'line_start': start, 'line_end': end,
                    'signature': sig, 'docstring': doc,
                    'source': snippet,
                })
            case 'schema':
                node_types = await db.read(
                    'SELECT DISTINCT symbol_type '
                    'FROM symbols', (),
                )
                edge_types = await db.read(
                    'SELECT DISTINCT edge_type, layer '
                    'FROM edges', (),
                )
                return json.dumps({
                    'node_types': [r[0] for r in node_types],
                    'edge_types': [
                        {'type': r[0], 'layer': r[1]}
                        for r in edge_types
                    ],
                })
            case 'neighbors':
                from ..storage.graph import get_neighbors
                rows = await get_neighbors(
                    db, target, direction='out', max_depth=1,
                )
                return json.dumps([
                    {
                        'name': r[1], 'file': r[2],
                        'type': r[3], 'depth': r[5],
                    }
                    for r in rows
                ])
            case _:
                return json.dumps(
                    {'error': f'Unknown mode: {mode}'},
                )

    @cortex.tool(
        name='cortex_trace',
        description=(
            'Multi-hop graph traversal. '
            'mode: calls, data_flow, cross_service'
        ),
    )
    async def cortex_trace(
        from_symbol: str,
        mode: str = 'calls',
        to_symbol: str | None = None,
        max_depth: int = 10,
        ctx: Context = None,
    ) -> str:
        from ..storage.graph import trace_path
        db = _get_db(ctx)
        max_depth = min(max_depth, 20)
        results = await trace_path(
            db, from_symbol, mode, max_depth, to_symbol,
        )
        return json.dumps(results)

    @cortex.tool(
        name='cortex_changes',
        description=(
            'Detect changed files (git diff) '
            'and compute blast radius'
        ),
    )
    async def cortex_changes(
        ref: str = 'HEAD~1',
        ctx: Context = None,
    ) -> str:
        import asyncio
        db = _get_db(ctx)
        project_dir = _get_project_dir(ctx)
        proc = await asyncio.create_subprocess_exec(
            'git', 'diff', '--name-only', ref,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        changed = [
            f for f in stdout.decode().strip().split('\n')
            if f
        ]
        results = []
        for file_path in changed:
            symbols = await db.read(
                'SELECT id, name, symbol_type '
                'FROM symbols WHERE file_path = ?',
                (str(project_dir / file_path),),
            )
            results.append({
                'file': file_path,
                'symbols_affected': len(symbols),
                'symbols': [
                    {'id': s[0], 'name': s[1], 'type': s[2]}
                    for s in symbols
                ],
            })
        return json.dumps({
            'ref': ref,
            'files_changed': len(changed),
            'details': results,
        })

    @cortex.tool(
        name='cortex_adr',
        description=(
            'Architecture Decision Records. '
            'action: create, list, get'
        ),
    )
    async def cortex_adr(
        action: str = 'list',
        title: str | None = None,
        context: str | None = None,
        decision: str | None = None,
        consequences: str | None = None,
        adr_id: str | None = None,
        ctx: Context = None,
    ) -> str:
        import uuid
        from datetime import datetime, timezone
        db = _get_db(ctx)
        match action:
            case 'create':
                if not title:
                    return json.dumps(
                        {'error': 'title is required'},
                    )
                new_id = str(uuid.uuid4())[:8]
                now = datetime.now(timezone.utc).isoformat()
                await db.write(
                    'INSERT INTO adrs '
                    '(id, title, status, context, decision, '
                    'consequences, created_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (new_id, title, 'proposed',
                     context or '', decision or '',
                     consequences or '', now),
                )
                return json.dumps({
                    'id': new_id, 'title': title,
                    'status': 'proposed',
                })
            case 'list':
                rows = await db.read(
                    'SELECT id, title, status, created_at '
                    'FROM adrs ORDER BY created_at', (),
                )
                return json.dumps([
                    {
                        'id': r[0], 'title': r[1],
                        'status': r[2], 'created_at': r[3],
                    }
                    for r in rows
                ])
            case 'get':
                if not adr_id:
                    return json.dumps(
                        {'error': 'adr_id is required'},
                    )
                rows = await db.read(
                    'SELECT * FROM adrs WHERE id = ?',
                    (adr_id,),
                )
                if not rows:
                    return json.dumps(
                        {'error': f'ADR not found: {adr_id}'},
                    )
                r = rows[0]
                return json.dumps({
                    'id': r[0], 'title': r[1],
                    'status': r[2], 'context': r[3],
                    'decision': r[4], 'consequences': r[5],
                    'created_at': r[6], 'updated_at': r[7],
                })
            case _:
                return json.dumps(
                    {'error': f'Unknown action: {action}'},
                )
