"""Incremental project indexer — stat pre-filter + SHA-256 + symbol extraction."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.db import CortexDB

SUPPORTED_EXTENSIONS = {
    '.py', '.pyw',
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    '.go',
    '.rs',
    '.ex', '.exs',
    '.sql',
}

MAX_FILE_SIZE = 500 * 1024  # 500KB

IGNORED_DIRS = {
    'node_modules', 'dist', '.next', '__pycache__', '.git',
    '.cortex', '.icpg', '.mnemos', 'venv', '.venv', '.tox',
    'build', 'target', '.mypy_cache', '.ruff_cache',
}

_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')
_IDENT_RE = re.compile(r'\b[a-zA-Z_]\w{2,}\b')


async def index_project(
    db: CortexDB,
    project_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    files = await asyncio.to_thread(_collect_files, project_dir)

    indexed_count = 0
    skipped_count = 0
    symbol_count = 0

    existing_files: set[str] = set()
    rows = await db.read(
        'SELECT file_path FROM file_index WHERE project_path = ?',
        (str(project_dir),),
    )
    existing_files = {r[0] for r in rows}

    current_files: set[str] = set()
    batch: list[tuple[str, tuple[Any, ...]]] = []

    for file_path in files:
        abs_path = str(file_path)
        current_files.add(abs_path)

        try:
            stat = file_path.stat()
        except OSError:
            skipped_count += 1
            continue
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size

        if not force:
            cached = await db.read(
                'SELECT mtime_ns, size FROM file_index WHERE file_path = ?',
                (abs_path,),
            )
            if cached and cached[0][0] == mtime_ns and cached[0][1] == size:
                skipped_count += 1
                continue

        content = await asyncio.to_thread(_read_file, file_path)
        if content is None:
            skipped_count += 1
            continue

        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]

        if not force:
            cached_hash = await db.read(
                'SELECT checksum FROM file_index WHERE file_path = ?',
                (abs_path,),
            )
            if cached_hash and cached_hash[0][0] == checksum:
                await db.write(
                    'UPDATE file_index SET mtime_ns = ?, size = ?, last_indexed = ? '
                    'WHERE file_path = ?',
                    (mtime_ns, size, now, abs_path),
                )
                skipped_count += 1
                continue

        from .fallback_parser import detect_language, parse_file

        language = detect_language(file_path)
        if not language:
            skipped_count += 1
            continue

        symbols = parse_file(file_path, content, language)
        line_count = content.count('\n') + 1

        from .complexity import compute_complexity
        complexities = compute_complexity(file_path, content, language)
        for sym in symbols:
            if sym.name in complexities:
                sym.complexity = complexities[sym.name]

        await _delete_edges_for_file(db, abs_path)
        await db.write(
            'DELETE FROM symbols WHERE file_path = ?', (abs_path,)
        )

        for sym in symbols:
            batch.append((
                'INSERT OR REPLACE INTO symbols '
                '(id, name, file_path, symbol_type, language, signature, checksum, '
                'line_start, line_end, docstring, complexity, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    sym.id, sym.name, str(sym.file_path), sym.symbol_type,
                    sym.language, sym.signature, sym.checksum,
                    sym.line_start, sym.line_end, sym.docstring,
                    sym.complexity, sym.created_at,
                ),
            ))

        batch.append((
            'INSERT OR REPLACE INTO file_index '
            '(file_path, project_path, language, mtime_ns, size, checksum, '
            'symbol_count, line_count, last_indexed) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (abs_path, str(project_dir), language, mtime_ns, size, checksum,
             len(symbols), line_count, now),
        ))

        batch.append((
            'INSERT OR REPLACE INTO source_fts (file_path, content, language) '
            'VALUES (?, ?, ?)',
            (abs_path, _augment_for_fts(content), language),
        ))

        await db.write_batch(batch)
        batch.clear()

        raw_edges = _extract_raw_edges(file_path, content, language)
        edge_batch = await _resolve_edges(db, raw_edges, abs_path, now)
        if edge_batch:
            await db.write_batch(edge_batch)

        indexed_count += 1
        symbol_count += len(symbols)

    if batch:
        await db.write_batch(batch)

    deleted_files = existing_files - current_files
    for deleted in deleted_files:
        await _delete_edges_for_file(db, deleted)
        await db.write('DELETE FROM symbols WHERE file_path = ?', (deleted,))
        await db.write('DELETE FROM file_index WHERE file_path = ?', (deleted,))

    await db.write(
        'INSERT OR REPLACE INTO projects (path, name, file_count, symbol_count, '
        'last_indexed, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (
            str(project_dir), project_dir.name,
            indexed_count + skipped_count, symbol_count, now, now,
        ),
    )

    return {
        'project': str(project_dir),
        'files_indexed': indexed_count,
        'files_skipped': skipped_count,
        'files_deleted': len(deleted_files),
        'symbols_extracted': symbol_count,
    }


def _extract_raw_edges(
    file_path: Path,
    content: str,
    language: str,
) -> list[Any]:
    from .edge_extractor import extract_python_edges, extract_ts_imports

    if language == 'python':
        return extract_python_edges(file_path, content)
    if language in ('typescript', 'javascript'):
        return extract_ts_imports(file_path, content)
    return []


_PHANTOM_EDGE_TYPES = frozenset({
    'RAISES', 'HANDLES', 'DECORATES', 'WRITES', 'HTTP_CALLS',
})


async def _resolve_edges(
    db: CortexDB,
    raw_edges: list[Any],
    abs_path: str,
    now: str,
) -> list[tuple[str, tuple[Any, ...]]]:
    local_syms = await db.read(
        'SELECT id, name FROM symbols WHERE file_path = ?',
        (abs_path,),
    )
    local_map = {r[1]: r[0] for r in local_syms}

    to_names = {e.to_name for e in raw_edges}
    global_map: dict[str, str] = {}
    for name in to_names:
        if name in local_map:
            global_map[name] = local_map[name]
        else:
            rows = await db.read(
                'SELECT id FROM symbols WHERE name = ? LIMIT 1',
                (name,),
            )
            if rows:
                global_map[name] = rows[0][0]

    batch: list[tuple[str, tuple[Any, ...]]] = []
    phantoms_created: set[str] = set()
    for raw in raw_edges:
        if raw.from_name == '__module__':
            from_id = local_map.get(
                next(iter(local_map), ''),
            )
        else:
            from_id = local_map.get(raw.from_name)
        to_id = global_map.get(raw.to_name)
        if not from_id:
            continue
        if not to_id and raw.edge_type in _PHANTOM_EDGE_TYPES:
            phantom_id = _phantom_id(raw.to_name)
            if phantom_id not in phantoms_created:
                phantoms_created.add(phantom_id)
                batch.append((
                    'INSERT OR IGNORE INTO symbols '
                    '(id, name, file_path, symbol_type, language, '
                    'checksum, created_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (phantom_id, raw.to_name, '__external__',
                     'external', 'any', '', now),
                ))
            to_id = phantom_id
        if not to_id:
            continue
        edge_id = str(uuid.uuid4())[:8]
        batch.append((
            'INSERT OR IGNORE INTO edges '
            '(id, from_id, from_type, to_id, to_type, '
            'edge_type, layer, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (edge_id, from_id, 'symbol', to_id, 'symbol',
             raw.edge_type, 'structure', now),
        ))
    return batch


def _phantom_id(name: str) -> str:
    import hashlib
    return hashlib.sha256(f'phantom:{name}'.encode()).hexdigest()[:16]


async def _delete_edges_for_file(
    db: CortexDB,
    file_path: str,
) -> None:
    await db.write(
        'DELETE FROM edges WHERE from_id IN '
        '(SELECT id FROM symbols WHERE file_path = ?)',
        (file_path,),
    )


def _augment_for_fts(content: str) -> str:
    identifiers = set(_IDENT_RE.findall(content))
    extra: set[str] = set()
    for ident in identifiers:
        parts = _CAMEL_RE.split(ident)
        if len(parts) > 1:
            extra.update(p.lower() for p in parts if len(p) > 1)
        if '_' in ident:
            extra.update(
                p.lower() for p in ident.split('_') if len(p) > 1
            )
    if extra:
        return content + '\n' + ' '.join(extra)
    return content


def _collect_files(project_dir: Path) -> list[Path]:
    gitignore_patterns = _load_gitignore(project_dir)
    result: list[Path] = []

    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [
            d for d in dirs
            if d not in IGNORED_DIRS and not d.startswith('.')
        ]

        for fname in filenames:
            fpath = Path(root) / fname
            if fpath.suffix not in SUPPORTED_EXTENSIONS:
                continue
            if fpath.stat().st_size > MAX_FILE_SIZE:
                continue
            if fpath.stat().st_size == 0:
                continue
            result.append(fpath)

    return result


def _read_file(file_path: Path) -> str | None:
    try:
        content = file_path.read_bytes()
        if b'\x00' in content[:8192]:
            return None
        return content.decode('utf-8', errors='replace')
    except OSError:
        return None


def _load_gitignore(project_dir: Path) -> list[str]:
    gitignore = project_dir / '.gitignore'
    if not gitignore.exists():
        return []
    return [
        line.strip() for line in gitignore.read_text().splitlines()
        if line.strip() and not line.startswith('#')
    ]
