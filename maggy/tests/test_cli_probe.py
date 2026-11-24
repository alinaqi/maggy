"""Tests for the CLI subprocess probes used by cli_discovery."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from maggy.adapters.cli_probe import (
    DEFAULT_OLLAMA_MODEL,
    clean_env,
    detect_ollama_model,
    get_help,
    get_version,
)


def _script(tmp_path: Path, body: str) -> str:
    path = tmp_path / "fakecli"
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_clean_env_drops_claudecode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    assert "CLAUDECODE" not in clean_env()


def test_get_help_passes_subcommand(tmp_path: Path) -> None:
    binary = _script(tmp_path, 'echo "args: $*"')
    assert get_help(binary, "exec") == "args: exec --help"


def test_get_help_missing_binary_is_empty(tmp_path: Path) -> None:
    assert get_help(str(tmp_path / "missing"), "") == ""


def test_get_version_first_line(tmp_path: Path) -> None:
    binary = _script(tmp_path, 'printf "tool 1.2\\nmore\\n"')
    assert get_version(binary) == "tool 1.2"


def test_detect_ollama_prefers_coder_model(tmp_path: Path) -> None:
    binary = _script(tmp_path, 'printf "NAME\\ndeepseek-coder-v2:latest x\\n"')
    assert detect_ollama_model(binary) == "deepseek-coder-v2"


def test_detect_ollama_falls_back_to_first_listed(tmp_path: Path) -> None:
    binary = _script(tmp_path, 'printf "NAME\\nmistral:7b x\\n"')
    assert detect_ollama_model(binary) == "mistral:7b"


def test_detect_ollama_missing_binary_uses_default(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing")
    assert detect_ollama_model(missing) == DEFAULT_OLLAMA_MODEL
