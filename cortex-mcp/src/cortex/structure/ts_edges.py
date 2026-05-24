"""TS/JS edge extraction — regex-based, all edge types."""

from __future__ import annotations

import re
from pathlib import Path

from .edge_extractor import RawEdge

_NAMED_IMPORT_RE = re.compile(r"import\s*\{([^}]+)\}\s*from\s*['\"]")
_DEFAULT_IMPORT_RE = re.compile(r"import\s+(\w+)\s+from\s*['\"]")
_REQUIRE_RE = re.compile(r"const\s+(\w+)\s*=\s*require\s*\(")

_CALL_SITE_RE = re.compile(r'(?<![.\w])([a-zA-Z_]\w*)\s*\(')
_CALL_EXCLUDE = frozenset({
    'if', 'for', 'while', 'switch', 'catch', 'return', 'throw',
    'new', 'typeof', 'instanceof', 'void', 'import', 'require',
    'export', 'from', 'class', 'function', 'async', 'await',
    'yield', 'delete', 'super', 'this', 'else', 'case',
    'try', 'finally', 'break', 'continue', 'var', 'let', 'const',
})

_FUNC_DECL_RE = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\('
    r'|(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(',
    re.MULTILINE,
)

_AWAIT_CALL_RE = re.compile(r'await\s+([a-zA-Z_]\w*)\s*\(')
_AWAIT_METHOD_RE = re.compile(r'await\s+\w+\.([a-zA-Z_]\w*)\s*\(')

_DECORATOR_RE = re.compile(
    r'@(\w+)(?:\([^)]*\))?\s*\n\s*'
    r'(?:export\s+)?(?:class|function)\s+(\w+)',
)

_HTTP_CALL_RE = re.compile(
    r'(?:fetch|axios|http|api|client)\s*'
    r'(?:\.\s*(get|post|put|delete|patch|head|options)\s*\(|\.request\s*\()'
    r'|fetch\s*\(',
)

_THROW_RE = re.compile(r'throw\s+new\s+(\w+)\s*\(')


def extract_all_ts_edges(
    file_path: Path, source: str,
) -> list[RawEdge]:
    fp = str(file_path)
    edges: list[RawEdge] = []
    edges.extend(_imports(source, fp))
    edges.extend(_calls(source, fp))
    edges.extend(_async_calls(source, fp))
    edges.extend(_decorates(source, fp))
    edges.extend(_http_calls(source, fp))
    edges.extend(_throws(source, fp))
    return edges


def _imports(source: str, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for match in _NAMED_IMPORT_RE.finditer(source):
        for name in match.group(1).split(','):
            cleaned = name.strip().split(' as ')[-1].strip()
            if cleaned:
                edges.append(RawEdge('__module__', cleaned, 'IMPORTS', fp))
    for match in _DEFAULT_IMPORT_RE.finditer(source):
        edges.append(RawEdge('__module__', match.group(1), 'IMPORTS', fp))
    for match in _REQUIRE_RE.finditer(source):
        edges.append(RawEdge('__module__', match.group(1), 'IMPORTS', fp))
    return edges


def _calls(source: str, fp: str) -> list[RawEdge]:
    func_positions = _find_func_positions(source)
    edges: list[RawEdge] = []
    seen: set[tuple[str, str]] = set()
    for match in _CALL_SITE_RE.finditer(source):
        call_name = match.group(1)
        if call_name in _CALL_EXCLUDE or len(call_name) < 2:
            continue
        line = source.count('\n', 0, match.start()) + 1
        caller = _enclosing_func(func_positions, line) or '__module__'
        key = (caller, call_name)
        if key not in seen and caller != call_name:
            seen.add(key)
            edges.append(RawEdge(caller, call_name, 'CALLS', fp))
    return edges


def _async_calls(source: str, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    func_positions = _find_func_positions(source)
    for match in _AWAIT_CALL_RE.finditer(source):
        name = match.group(1)
        if name in _CALL_EXCLUDE or name in seen:
            continue
        seen.add(name)
        line = source.count('\n', 0, match.start()) + 1
        caller = _enclosing_func(func_positions, line) or '__module__'
        edges.append(RawEdge(caller, name, 'ASYNC_CALLS', fp))
    for match in _AWAIT_METHOD_RE.finditer(source):
        name = match.group(1)
        if name in _CALL_EXCLUDE or name in seen:
            continue
        seen.add(name)
        line = source.count('\n', 0, match.start()) + 1
        caller = _enclosing_func(func_positions, line) or '__module__'
        edges.append(RawEdge(caller, name, 'ASYNC_CALLS', fp))
    return edges


def _decorates(source: str, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for match in _DECORATOR_RE.finditer(source):
        edges.append(RawEdge(match.group(1), match.group(2), 'DECORATES', fp))
    return edges


def _http_calls(source: str, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    func_positions = _find_func_positions(source)
    for match in _HTTP_CALL_RE.finditer(source):
        line = source.count('\n', 0, match.start()) + 1
        caller = _enclosing_func(func_positions, line) or '__module__'
        method = match.group(1) or 'GET'
        edges.append(RawEdge(caller, method.upper(), 'HTTP_CALLS', fp))
    return edges


def _throws(source: str, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    func_positions = _find_func_positions(source)
    seen: set[tuple[str, str]] = set()
    for match in _THROW_RE.finditer(source):
        exc_name = match.group(1)
        line = source.count('\n', 0, match.start()) + 1
        caller = _enclosing_func(func_positions, line) or '__module__'
        key = (caller, exc_name)
        if key not in seen:
            seen.add(key)
            edges.append(RawEdge(caller, exc_name, 'RAISES', fp))
    return edges


def _find_func_positions(source: str) -> list[tuple[str, int]]:
    positions: list[tuple[str, int]] = []
    for match in _FUNC_DECL_RE.finditer(source):
        name = match.group(1) or match.group(2)
        if name:
            line = source.count('\n', 0, match.start()) + 1
            positions.append((name, line))
    return positions


def _enclosing_func(
    positions: list[tuple[str, int]], line: int,
) -> str | None:
    result: str | None = None
    for name, start_line in positions:
        if start_line <= line:
            result = name
        else:
            break
    return result
