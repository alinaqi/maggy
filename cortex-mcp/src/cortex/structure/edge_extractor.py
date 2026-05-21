"""Extract CALLS and IMPORTS edges from parsed source."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawEdge:
    from_name: str
    to_name: str
    edge_type: str
    from_file: str


def extract_python_edges(
    file_path: Path,
    source: str,
) -> list[RawEdge]:
    """Extract CALLS and IMPORTS edges from Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    fp = str(file_path)
    edges: list[RawEdge] = []
    edges.extend(_python_imports(tree, fp))
    edges.extend(_python_calls(tree, fp))
    return edges


def extract_ts_imports(
    file_path: Path,
    source: str,
) -> list[RawEdge]:
    """Extract IMPORTS edges from TS/JS source using regex."""
    fp = str(file_path)
    edges: list[RawEdge] = []
    edges.extend(_ts_named_imports(source, fp))
    edges.extend(_ts_default_imports(source, fp))
    edges.extend(_ts_require_imports(source, fp))
    return edges


def _python_imports(
    tree: ast.Module,
    fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                edges.append(RawEdge("__module__", name, "IMPORTS", fp))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                edges.append(RawEdge("__module__", name, "IMPORTS", fp))
    return edges


def _python_calls(
    tree: ast.Module,
    fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for call_name in _walk_calls(node):
            edges.append(RawEdge(func_name, call_name, "CALLS", fp))
    return edges


def _walk_calls(node: ast.AST) -> list[str]:
    """Extract called function names from a function body."""
    names: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if name:
            names.append(name)
    return names


def _call_name(node: ast.Call) -> str | None:
    """Extract the function/method name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


_NAMED_IMPORT_RE = re.compile(
    r"import\s*\{([^}]+)\}\s*from\s*['\"]"
)

_DEFAULT_IMPORT_RE = re.compile(
    r"import\s+(\w+)\s+from\s*['\"]"
)

_REQUIRE_RE = re.compile(
    r"const\s+(\w+)\s*=\s*require\s*\("
)


def _ts_named_imports(
    source: str,
    fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for match in _NAMED_IMPORT_RE.finditer(source):
        names_str = match.group(1)
        for name in names_str.split(","):
            cleaned = name.strip().split(" as ")[-1].strip()
            if cleaned:
                edges.append(RawEdge("__module__", cleaned, "IMPORTS", fp))
    return edges


def _ts_default_imports(
    source: str,
    fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for match in _DEFAULT_IMPORT_RE.finditer(source):
        edges.append(RawEdge("__module__", match.group(1), "IMPORTS", fp))
    return edges


def _ts_require_imports(
    source: str,
    fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for match in _REQUIRE_RE.finditer(source):
        edges.append(RawEdge("__module__", match.group(1), "IMPORTS", fp))
    return edges
