"""Shared test fixtures for Cortex MCP tests."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with sample files."""
    src = tmp_path / 'src'
    src.mkdir()

    (src / 'main.py').write_text(
        'def main():\n'
        '    app = create_app()\n'
        '    app.run()\n'
        '\n'
        'def create_app():\n'
        '    return App()\n'
        '\n'
        'class App:\n'
        '    def run(self):\n'
        '        pass\n',
        encoding='utf-8',
    )

    (src / 'utils.py').write_text(
        'def validate_token(token: str) -> bool:\n'
        '    return len(token) > 0\n'
        '\n'
        'def hash_password(password: str) -> str:\n'
        '    return password[::-1]\n',
        encoding='utf-8',
    )

    ts_dir = src / 'frontend'
    ts_dir.mkdir()
    (ts_dir / 'app.ts').write_text(
        'export function initApp(): void {\n'
        '  console.log("init")\n'
        '}\n'
        '\n'
        'export class Router {\n'
        '  navigate(path: string): void {}\n'
        '}\n',
        encoding='utf-8',
    )

    (tmp_path / '.gitignore').write_text(
        'node_modules/\ndist/\n__pycache__/\n.cortex/\n',
        encoding='utf-8',
    )

    return tmp_path


@pytest.fixture
def cortex_dir(tmp_path: Path) -> Path:
    """Create .cortex directory and return the DB path."""
    cortex = tmp_path / '.cortex'
    cortex.mkdir()
    return cortex
