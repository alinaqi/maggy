"""Fallback symbol extraction using ast (Python) and regex (other languages).

Ported from iCPG symbols.py — provides zero-dependency parsing when
tree-sitter is unavailable.
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

from .models import Symbol

LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".scala": "scala",
    ".lua": "lua",
    ".vue": "vue",
    ".svelte": "svelte",
    ".ex": "elixir",
    ".exs": "elixir",
}


def detect_language(file_path: Path) -> str | None:
    return LANG_MAP.get(file_path.suffix.lower())


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _line_number_at(source: str, offset: int) -> int:
    """1-based line number for a character offset."""
    return source.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# Python extraction (AST-based)
# ---------------------------------------------------------------------------

_ROUTE_METHODS = frozenset({"get", "post", "put", "delete", "patch", "route"})


def _extract_route_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    """Return 'METHOD /path' if the function has a route decorator."""
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func if hasattr(dec, "func") else None
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _ROUTE_METHODS:
            continue
        if dec.args and isinstance(dec.args[0], ast.Constant):
            path = dec.args[0].value
            method = func.attr.upper()
            return f"{method} {path}"
    return None


def _python_func_sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    for a in node.args.args:
        ann = ""
        if a.annotation:
            ann = f": {ast.dump(a.annotation)}"
        args.append(f"{a.arg}{ann}")
    ret = ""
    if node.returns:
        ret = f" -> {ast.dump(node.returns)}"
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)}){ret}"


def _python_class_sig(node: ast.ClassDef) -> str:
    bases = [ast.dump(b) for b in node.bases]
    if bases:
        return f"class {node.name}({', '.join(bases)})"
    return f"class {node.name}"


def _extract_python(
    file_path: Path,
    source: str,
) -> list[Symbol]:
    symbols: list[Symbol] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    fp = str(file_path)

    class_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_nodes.update(id(child) for child in node.body)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            body = ast.get_source_segment(source, node) or ""
            docstring = ast.get_docstring(node)
            symbols.append(Symbol(
                name=node.name,
                file_path=fp,
                symbol_type="class",
                language="python",
                signature=_python_class_sig(node),
                checksum=_checksum(body),
                line_start=node.lineno,
                line_end=node.end_lineno,
                docstring=docstring,
            ))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.get_source_segment(source, node) or ""
            docstring = ast.get_docstring(node)
            stype = "method" if id(node) in class_nodes else "function"
            symbols.append(Symbol(
                name=node.name,
                file_path=fp,
                symbol_type=stype,
                language="python",
                signature=_python_func_sig(node),
                checksum=_checksum(body),
                line_start=node.lineno,
                line_end=node.end_lineno,
                docstring=docstring,
            ))
            route_name = _extract_route_decorator(node)
            if route_name:
                symbols.append(Symbol(
                    name=route_name,
                    file_path=fp,
                    symbol_type="route",
                    language="python",
                    signature=route_name,
                    checksum=_checksum(route_name),
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                ))

    return symbols


# ---------------------------------------------------------------------------
# TypeScript / JavaScript extraction (regex)
# ---------------------------------------------------------------------------

_TS_PATTERNS: list[tuple[str, str]] = [
    (r"export\s+(?:async\s+)?function\s+(\w+)\s*\([^)]*\)", "function"),
    (r"export\s+(?:abstract\s+)?class\s+(\w+)", "class"),
    (r"export\s+const\s+(\w+)\s*[=:]", "constant"),
    (r"export\s+interface\s+(\w+)", "interface"),
    (r"export\s+type\s+(\w+)", "type"),
    (
        r"export\s+const\s+((?:[A-Z]\w+))\s*=\s*(?:\([^)]*\)|[^=])\s*=>",
        "component",
    ),
    (r"export\s+(?:async\s+)?function\s+(use\w+)", "hook"),
]

_TS_ROUTE_RE = re.compile(
    r"(?:app|router)\.(get|post|put|delete|patch)"
    r"\s*\(\s*['\"]([^'\"]+)['\"]"
)

_TS_METHOD_RE = re.compile(
    r"^\s+(?:(?:private|protected|public|static|readonly)\s+)*"
    r"(?:(?:async|get|set)\s+)?(\w+)\s*\([^)]*\)\s*"
    r"(?::\s*\S+)?\s*\{",
    re.MULTILINE,
)

_TS_METHOD_EXCLUDE = frozenset({
    "if", "for", "while", "switch", "catch",
    "constructor", "return", "throw", "new",
})


def _ts_sig_at(source: str, match: re.Match[str]) -> str:
    start = source.rfind("\n", 0, match.start()) + 1
    end = source.find("\n", match.end())
    if end == -1:
        end = len(source)
    return source[start:end].strip()


def _extract_typescript(
    file_path: Path,
    source: str,
) -> list[Symbol]:
    lang = (
        "typescript"
        if file_path.suffix in (".ts", ".tsx")
        else "javascript"
    )
    fp = str(file_path)
    seen: set[str] = set()
    symbols = _ts_exports(source, fp, lang)
    for s in symbols:
        seen.add(s.name)
    symbols += _ts_routes(source, fp, lang)
    symbols += _ts_methods(source, fp, lang)
    symbols = _dedup_symbols(symbols, seen)
    return symbols


def _dedup_symbols(
    symbols: list[Symbol], pre_seen: set[str],
) -> list[Symbol]:
    result: list[Symbol] = []
    seen = set(pre_seen)
    for s in symbols:
        key = (s.name, s.symbol_type)
        if s.symbol_type in ("route",) or key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _ts_exports(source: str, fp: str, lang: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    seen: set[str] = set()
    for pattern, stype in _TS_PATTERNS:
        for match in re.finditer(pattern, source):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)
            sig = _ts_sig_at(source, match)
            symbols.append(Symbol(
                name=name,
                file_path=fp,
                symbol_type=stype,
                language=lang,
                signature=sig[:200],
                checksum=_checksum(sig),
                line_start=_line_number_at(source, match.start()),
                line_end=_line_number_at(source, match.end()),
            ))
    return symbols


def _ts_routes(source: str, fp: str, lang: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    for match in _TS_ROUTE_RE.finditer(source):
        method = match.group(1).upper()
        path = match.group(2)
        name = f"{method} {path}"
        symbols.append(Symbol(
            name=name,
            file_path=fp,
            symbol_type="route",
            language=lang,
            signature=name,
            checksum=_checksum(name),
            line_start=_line_number_at(source, match.start()),
            line_end=_line_number_at(source, match.end()),
        ))
    return symbols


def _ts_methods(source: str, fp: str, lang: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    for match in _TS_METHOD_RE.finditer(source):
        name = match.group(1)
        if name in _TS_METHOD_EXCLUDE:
            continue
        sig = _ts_sig_at(source, match)
        symbols.append(Symbol(
            name=name,
            file_path=fp,
            symbol_type="method",
            language=lang,
            signature=sig[:200],
            checksum=_checksum(sig),
            line_start=_line_number_at(source, match.start()),
            line_end=_line_number_at(source, match.end()),
        ))
    return symbols


# ---------------------------------------------------------------------------
# Go extraction (regex)
# ---------------------------------------------------------------------------

_GO_PATTERNS: list[tuple[str, str]] = [
    (r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", "function"),
    (r"type\s+(\w+)\s+struct\s*\{", "class"),
    (r"type\s+(\w+)\s+interface\s*\{", "interface"),
]


def _extract_go(
    file_path: Path,
    source: str,
) -> list[Symbol]:
    symbols: list[Symbol] = []
    seen: set[str] = set()
    fp = str(file_path)

    for pattern, stype in _GO_PATTERNS:
        for match in re.finditer(pattern, source):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)

            line_start_offset = source.rfind("\n", 0, match.start()) + 1
            line_end_offset = source.find("\n", match.end())
            if line_end_offset == -1:
                line_end_offset = len(source)
            sig = source[line_start_offset:line_end_offset].strip()

            symbols.append(Symbol(
                name=name,
                file_path=fp,
                symbol_type=stype,
                language="go",
                signature=sig[:200],
                checksum=_checksum(sig),
                line_start=_line_number_at(source, match.start()),
                line_end=_line_number_at(source, line_end_offset),
            ))

    return symbols


# ---------------------------------------------------------------------------
# Rust extraction (regex)
# ---------------------------------------------------------------------------

_RUST_PATTERNS: list[tuple[str, str]] = [
    (r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", "function"),
    (r"(?:pub\s+)?struct\s+(\w+)", "class"),
    (r"(?:pub\s+)?enum\s+(\w+)", "type"),
    (r"(?:pub\s+)?trait\s+(\w+)", "interface"),
    (r"impl\s+(\w+)", "class"),
]


def _extract_rust(
    file_path: Path,
    source: str,
) -> list[Symbol]:
    symbols: list[Symbol] = []
    seen: set[str] = set()
    fp = str(file_path)

    for pattern, stype in _RUST_PATTERNS:
        for match in re.finditer(pattern, source):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)

            line_start_offset = source.rfind("\n", 0, match.start()) + 1
            line_end_offset = source.find("\n", match.end())
            if line_end_offset == -1:
                line_end_offset = len(source)
            sig = source[line_start_offset:line_end_offset].strip()

            symbols.append(Symbol(
                name=name,
                file_path=fp,
                symbol_type=stype,
                language="rust",
                signature=sig[:200],
                checksum=_checksum(sig),
                line_start=_line_number_at(source, match.start()),
                line_end=_line_number_at(source, line_end_offset),
            ))

    return symbols


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, object] = {
    "python": _extract_python,
    "typescript": _extract_typescript,
    "javascript": _extract_typescript,
    "go": _extract_go,
    "rust": _extract_rust,
}


def parse_file(
    file_path: Path,
    content: str,
    language: str,
) -> list[Symbol]:
    """Extract symbols from source content.

    This is the primary public API. It dispatches to the appropriate
    language-specific extractor or returns an empty list for
    unsupported languages.
    """
    extractor = _EXTRACTORS.get(language)
    if extractor is None:
        return []
    return extractor(file_path, content)  # type: ignore[operator]
