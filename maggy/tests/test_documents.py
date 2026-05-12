"""Tests for document text extraction and chat integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from maggy.services.documents import (
    extract_document_path,
    extract_text,
)


@pytest.fixture()
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text("name,age\nAlice,30\nBob,25\n")
    return p


@pytest.fixture()
def json_file(tmp_path: Path) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"key": "value", "n": 42}))
    return p


@pytest.fixture()
def txt_file(tmp_path: Path) -> Path:
    p = tmp_path / "notes.txt"
    p.write_text("Meeting notes: discuss Q3 targets.")
    return p


class TestExtractDocumentPath:
    """Detect document file paths in chat messages."""

    def test_detects_csv(self, csv_file):
        result = extract_document_path(f"{csv_file} analyze this")
        assert result is not None
        assert result[0] == str(csv_file)
        assert result[1] == "analyze this"

    def test_detects_json(self, json_file):
        result = extract_document_path(f"review {json_file}")
        assert result is not None

    def test_detects_txt(self, txt_file):
        result = extract_document_path(f"{txt_file} summarize")
        assert result is not None

    def test_no_document_returns_none(self):
        assert extract_document_path("fix the bug") is None

    def test_nonexistent_file_returns_none(self):
        assert extract_document_path("/tmp/nope.xlsx") is None

    def test_image_not_matched(self, tmp_path):
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG")
        assert extract_document_path(str(img)) is None


class TestExtractText:
    """Text extraction from various file formats."""

    def test_csv_extraction(self, csv_file):
        text = extract_text(str(csv_file))
        assert "Alice" in text
        assert "30" in text

    def test_json_extraction(self, json_file):
        text = extract_text(str(json_file))
        assert "key" in text
        assert "42" in text

    def test_txt_extraction(self, txt_file):
        text = extract_text(str(txt_file))
        assert "Q3 targets" in text

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("stuff")
        text = extract_text(str(f))
        assert "not supported" in text.lower()

    def test_excel_auto_installs_openpyxl(self, tmp_path):
        f = tmp_path / "report.xlsx"
        f.write_bytes(b"PK\x03\x04")
        installed = []

        def fake_pip(name):
            installed.append(name)

        from maggy.services import auto_deps
        original = auto_deps.importlib.import_module

        def patched(name):
            if name == "openpyxl":
                raise ImportError("no openpyxl")
            return original(name)

        with patch.object(
            auto_deps.importlib, "import_module", patched,
        ), patch(
            "maggy.services.auto_deps._pip_install",
            side_effect=fake_pip,
        ):
            text = extract_text(str(f))
        assert len(installed) == 1
        assert installed[0] == "openpyxl"

    def test_truncates_large_files(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * 20_000)
        text = extract_text(str(f))
        assert len(text) <= 8500
