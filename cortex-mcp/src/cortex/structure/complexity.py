"""Cyclomatic complexity calculation for Python (AST) and TS/JS (regex)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

_DECISION_NODE_TYPES = (
    ast.If, ast.For, ast.While, ast.ExceptHandler,
    ast.With, ast.Assert, ast.IfExp,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)


def python_complexity(source: str) -> dict[str, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    result: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        result[node.name] = _py_func_complexity(node)
    return result


def _py_func_complexity(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, _DECISION_NODE_TYPES):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


_TS_DECISION_RE = re.compile(
    r'\b(?:if|else\s+if|for|while|do|catch|case)\b'
    r'|\?\s*[^:]*\s*:'
    r'|&&|\|\|',
)

_TS_FUNC_RE = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)[^{]*\{'
    r'|(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)[^{]*=>\s*\{',
)


def ts_complexity(source: str) -> dict[str, int]:
    result: dict[str, int] = {}
    func_ranges = _find_ts_func_ranges(source)
    for name, start, end in func_ranges:
        body = source[start:end]
        complexity = 1 + len(_TS_DECISION_RE.findall(body))
        result[name] = complexity
    return result


def _find_ts_func_ranges(
    source: str,
) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    for match in _TS_FUNC_RE.finditer(source):
        name = match.group(1) or match.group(2)
        if not name:
            continue
        brace_pos = source.find('{', match.end() - 1)
        if brace_pos == -1:
            continue
        end = _find_closing_brace(source, brace_pos)
        ranges.append((name, brace_pos, end))
    return ranges


def _find_closing_brace(source: str, start: int) -> int:
    depth = 0
    i = start
    in_string: str | None = None
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == in_string and source[i - 1:i] != '\\':
                in_string = None
        elif ch in ('"', "'", '`'):
            in_string = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(source)


def compute_complexity(
    file_path: Path, source: str, language: str,
) -> dict[str, int]:
    if language == 'python':
        return python_complexity(source)
    if language in ('typescript', 'javascript'):
        return ts_complexity(source)
    return {}
