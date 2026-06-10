"""Python edge extraction — AST-based, all edge types."""

from __future__ import annotations

import ast
from pathlib import Path

from .edge_extractor import RawEdge

_WRITE_METHODS = frozenset({
    'write', 'execute', 'save', 'commit', 'send', 'post', 'put',
    'insert', 'update', 'create', 'set', 'store', 'push', 'emit',
    'delete', 'remove', 'append', 'extend', 'add',
})


def extract_all_python_edges(
    file_path: Path, source: str,
) -> list[RawEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    fp = str(file_path)
    edges: list[RawEdge] = []
    edges.extend(_imports(tree, fp))
    funcs = _collect_functions(tree)
    class_methods = _collect_class_methods(tree)
    for func_name, node in funcs:
        edges.extend(_calls_in(func_name, node, fp))
        edges.extend(_async_calls_in(func_name, node, fp))
        edges.extend(_raises_in(func_name, node, fp))
        edges.extend(_handles_in(func_name, node, fp))
        edges.extend(_writes_in(func_name, node, fp))
        edges.extend(_usage_in(func_name, node, fp))
    edges.extend(_defines_method(class_methods, fp))
    edges.extend(_decorates(tree, fp))
    edges.extend(_tests(funcs, fp))
    return edges


def _collect_functions(
    tree: ast.Module,
) -> list[tuple[str, ast.AST]]:
    return [
        (n.name, n) for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _collect_class_methods(
    tree: ast.Module,
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                pairs.append((node.name, child.name))
    return pairs


def _imports(tree: ast.Module, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(RawEdge(
                    '__module__', alias.asname or alias.name, 'IMPORTS', fp,
                ))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                edges.append(RawEdge(
                    '__module__', alias.asname or alias.name, 'IMPORTS', fp,
                ))
    return edges


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _calls_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if name and name not in seen:
            seen.add(name)
            edges.append(RawEdge(func_name, name, 'CALLS', fp))
    return edges


def _async_calls_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Await):
            continue
        if not isinstance(child.value, ast.Call):
            continue
        name = _call_name(child.value)
        if name and name not in seen:
            seen.add(name)
            edges.append(RawEdge(func_name, name, 'ASYNC_CALLS', fp))
    return edges


def _raises_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise) or not child.exc:
            continue
        exc = child.exc
        if isinstance(exc, ast.Call):
            name = _call_name(exc)
        elif isinstance(exc, ast.Name):
            name = exc.id
        else:
            name = None
        if name and name not in seen:
            seen.add(name)
            edges.append(RawEdge(func_name, name, 'RAISES', fp))
    return edges


def _handles_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.ExceptHandler) or not child.type:
            continue
        if isinstance(child.type, ast.Name):
            name = child.type.id
        elif isinstance(child.type, ast.Attribute):
            name = child.type.attr
        elif isinstance(child.type, ast.Tuple):
            for elt in child.type.elts:
                if isinstance(elt, ast.Name) and elt.id not in seen:
                    seen.add(elt.id)
                    edges.append(RawEdge(func_name, elt.id, 'HANDLES', fp))
            continue
        else:
            continue
        if name not in seen:
            seen.add(name)
            edges.append(RawEdge(func_name, name, 'HANDLES', fp))
    return edges


def _writes_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if child.func.attr not in _WRITE_METHODS:
            continue
        name = child.func.attr
        if name not in seen:
            seen.add(name)
            edges.append(RawEdge(func_name, name, 'WRITES', fp))
    return edges


def _usage_in(
    func_name: str, node: ast.AST, fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    seen: set[str] = set()
    call_targets: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            n = _call_name(child)
            if n:
                call_targets.add(n)
    for child in ast.walk(node):
        if not isinstance(child, ast.Name):
            continue
        name = child.id
        if name in call_targets or name in seen:
            continue
        if name.startswith('_') or len(name) < 2:
            continue
        seen.add(name)
        edges.append(RawEdge(func_name, name, 'USAGE', fp))
    return edges


def _defines_method(
    pairs: list[tuple[str, str]], fp: str,
) -> list[RawEdge]:
    return [
        RawEdge(cls, method, 'DEFINES_METHOD', fp)
        for cls, method in pairs
    ]


def _decorates(tree: ast.Module, fp: str) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for node in ast.walk(tree):
        if not isinstance(node, (
            ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
        )):
            continue
        for dec in node.decorator_list:
            name = _dec_name(dec)
            if name:
                edges.append(RawEdge(name, node.name, 'DECORATES', fp))
    return edges


def _dec_name(dec: ast.expr) -> str | None:
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Call):
        return _dec_name(dec.func)
    return None


def _tests(
    funcs: list[tuple[str, ast.AST]], fp: str,
) -> list[RawEdge]:
    edges: list[RawEdge] = []
    for func_name, node in funcs:
        if not func_name.startswith('test_'):
            continue
        tested = func_name[5:]
        if tested:
            edges.append(RawEdge(func_name, tested, 'TESTS', fp))
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            name = _call_name(child)
            if name and name != func_name and not name.startswith('assert'):
                edges.append(RawEdge(func_name, name, 'TESTS', fp))
    return edges
