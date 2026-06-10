"""Git-based edge extraction — FILE_CHANGES_WITH co-change analysis."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

from .edge_extractor import RawEdge

CO_CHANGE_THRESHOLD = 3


async def extract_git_cochange(
    project_dir: Path, max_commits: int = 500,
) -> list[RawEdge]:
    try:
        proc = await asyncio.create_subprocess_exec(
            'git', 'log', '--name-only', '--format=COMMIT',
            f'-{max_commits}',
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []
    except FileNotFoundError:
        return []

    commits = _parse_commit_files(stdout.decode())
    cochange = _build_cochange_matrix(commits)
    return _matrix_to_edges(cochange, str(project_dir))


def _parse_commit_files(output: str) -> list[list[str]]:
    commits: list[list[str]] = []
    current: list[str] = []
    for line in output.strip().split('\n'):
        if line == 'COMMIT':
            if current:
                commits.append(current)
            current = []
        elif line.strip():
            current.append(line.strip())
    if current:
        commits.append(current)
    return commits


def _build_cochange_matrix(
    commits: list[list[str]],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for files in commits:
        if len(files) > 20:
            continue
        for i, f1 in enumerate(files):
            for f2 in files[i + 1:]:
                key = (min(f1, f2), max(f1, f2))
                counts[key] += 1
    return {k: v for k, v in counts.items() if v >= CO_CHANGE_THRESHOLD}


def _matrix_to_edges(
    cochange: dict[tuple[str, str], int], project_dir: str,
) -> list[RawEdge]:
    return [
        RawEdge(f1, f2, 'FILE_CHANGES_WITH', project_dir)
        for (f1, f2) in cochange
    ]
