"""Source code snippet extraction with context lines."""

from __future__ import annotations

import asyncio
from pathlib import Path


async def extract_snippet(
    file_path: Path,
    line_start: int,
    line_end: int,
    context_lines: int = 3,
) -> str:
    return await asyncio.to_thread(
        _read_snippet, file_path, line_start, line_end, context_lines
    )


def _read_snippet(
    file_path: Path,
    line_start: int,
    line_end: int,
    context_lines: int,
) -> str:
    if not file_path.exists():
        return f'# File not found: {file_path}'

    lines = file_path.read_text(encoding='utf-8', errors='replace').splitlines()
    start = max(0, line_start - 1 - context_lines)
    end = min(len(lines), line_end + context_lines)

    numbered = []
    for i in range(start, end):
        prefix = '>' if line_start - 1 <= i < line_end else ' '
        numbered.append(f'{prefix} {i + 1:4d} | {lines[i]}')

    return '\n'.join(numbered)
