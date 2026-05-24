"""Edge extraction coordinator — delegates to language-specific modules.

RawEdge is defined here so language modules can import it without cycles.
Legacy functions re-export from python_edges/ts_edges for backward compat.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawEdge:
    from_name: str
    to_name: str
    edge_type: str
    from_file: str


def extract_python_edges(
    file_path: Path, source: str,
) -> list[RawEdge]:
    from .python_edges import extract_all_python_edges
    return extract_all_python_edges(file_path, source)


def extract_ts_imports(
    file_path: Path, source: str,
) -> list[RawEdge]:
    from .ts_edges import extract_all_ts_edges
    return extract_all_ts_edges(file_path, source)


def extract_ts_calls(
    file_path: Path, source: str,
) -> list[RawEdge]:
    from .ts_edges import extract_all_ts_edges
    return [
        e for e in extract_all_ts_edges(file_path, source)
        if e.edge_type == 'CALLS'
    ]
