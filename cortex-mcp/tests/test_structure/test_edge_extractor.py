"""Unit tests for edge extraction from Python and TS/JS source."""

from __future__ import annotations

from pathlib import Path

from cortex.structure.edge_extractor import (
    RawEdge,
    extract_python_edges,
    extract_ts_imports,
)


class TestPythonImports:
    def test_extracts_import_statement(self) -> None:
        source = "import os\n"
        edges = extract_python_edges(Path("app.py"), source)
        names = [(e.from_name, e.to_name, e.edge_type) for e in edges]
        assert ("__module__", "os", "IMPORTS") in names

    def test_extracts_from_import(self) -> None:
        source = "from pathlib import Path\n"
        edges = extract_python_edges(Path("app.py"), source)
        names = [(e.from_name, e.to_name, e.edge_type) for e in edges]
        assert ("__module__", "Path", "IMPORTS") in names

    def test_extracts_multiple_from_imports(self) -> None:
        source = "from typing import List, Dict, Optional\n"
        edges = extract_python_edges(Path("app.py"), source)
        imported = [e.to_name for e in edges if e.edge_type == "IMPORTS"]
        assert "List" in imported
        assert "Dict" in imported
        assert "Optional" in imported

    def test_handles_relative_imports(self) -> None:
        source = "from .utils import validate\n"
        edges = extract_python_edges(Path("app.py"), source)
        imported = [e.to_name for e in edges if e.edge_type == "IMPORTS"]
        assert "validate" in imported


class TestPythonCalls:
    def test_extracts_function_call(self) -> None:
        source = "def main():\n    run()\n"
        edges = extract_python_edges(Path("app.py"), source)
        calls = [
            (e.from_name, e.to_name)
            for e in edges if e.edge_type == "CALLS"
        ]
        assert ("main", "run") in calls

    def test_extracts_method_call(self) -> None:
        source = "def main():\n    app.start()\n"
        edges = extract_python_edges(Path("app.py"), source)
        calls = [
            (e.from_name, e.to_name)
            for e in edges if e.edge_type == "CALLS"
        ]
        assert ("main", "start") in calls

    def test_extracts_calls_inside_function(self) -> None:
        source = (
            "def process():\n"
            "    data = fetch()\n"
            "    result = transform(data)\n"
            "    save(result)\n"
        )
        edges = extract_python_edges(Path("app.py"), source)
        calls = [
            (e.from_name, e.to_name)
            for e in edges if e.edge_type == "CALLS"
        ]
        assert ("process", "fetch") in calls
        assert ("process", "transform") in calls
        assert ("process", "save") in calls

    def test_handles_chained_calls(self) -> None:
        source = "def main():\n    a.b.c()\n"
        edges = extract_python_edges(Path("app.py"), source)
        calls = [
            (e.from_name, e.to_name)
            for e in edges if e.edge_type == "CALLS"
        ]
        assert ("main", "c") in calls

    def test_handles_no_calls(self) -> None:
        source = "def noop():\n    x = 1\n"
        edges = extract_python_edges(Path("app.py"), source)
        calls = [e for e in edges if e.edge_type == "CALLS"]
        assert len(calls) == 0

    def test_async_function_calls(self) -> None:
        source = "async def handler():\n    await fetch()\n"
        edges = extract_python_edges(Path("app.py"), source)
        calls = [
            (e.from_name, e.to_name)
            for e in edges if e.edge_type == "CALLS"
        ]
        assert ("handler", "fetch") in calls

    def test_syntax_error_returns_empty(self) -> None:
        source = "def broken(:\n"
        edges = extract_python_edges(Path("app.py"), source)
        assert edges == []


class TestTsImports:
    def test_extracts_named_import(self) -> None:
        source = "import { Router, App } from './app'\n"
        edges = extract_ts_imports(Path("index.ts"), source)
        imported = [e.to_name for e in edges]
        assert "Router" in imported
        assert "App" in imported

    def test_extracts_default_import(self) -> None:
        source = "import React from 'react'\n"
        edges = extract_ts_imports(Path("index.ts"), source)
        imported = [e.to_name for e in edges]
        assert "React" in imported

    def test_extracts_require(self) -> None:
        source = "const express = require('express')\n"
        edges = extract_ts_imports(Path("index.js"), source)
        imported = [e.to_name for e in edges]
        assert "express" in imported

    def test_all_edges_are_imports(self) -> None:
        source = "import { X } from './mod'\n"
        edges = extract_ts_imports(Path("index.ts"), source)
        assert all(e.edge_type == "IMPORTS" for e in edges)

    def test_from_file_set_correctly(self) -> None:
        source = "import { X } from './mod'\n"
        edges = extract_ts_imports(Path("index.ts"), source)
        assert all(e.from_file == "index.ts" for e in edges)
