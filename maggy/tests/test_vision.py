"""Tests for Maggy vision service — Ollama Qwen3-VL integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maggy.services.vision import analyze_image, extract_image_path


@pytest.fixture()
def png_file(tmp_path: Path) -> Path:
    """Create a tiny valid PNG file."""
    p = tmp_path / "test.png"
    # Minimal 1x1 PNG
    p.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
    )
    return p


def test_analyze_missing_file():
    """Nonexistent path yields error chunk."""
    chunks = list(analyze_image("/no/such/file.png"))
    assert any(c["type"] == "error" for c in chunks)


def test_analyze_bad_extension(tmp_path: Path):
    """Non-image extension yields error chunk."""
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    chunks = list(analyze_image(str(txt)))
    assert any(c["type"] == "error" for c in chunks)


def test_analyze_streams_response(png_file: Path):
    """Mock Ollama API returns streamed text + done."""
    lines = [
        json.dumps({"message": {"content": "A "}}),
        json.dumps({"message": {"content": "button"}}),
        json.dumps({"done": True}),
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = iter(lines)
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("maggy.services.vision.httpx.stream",
               return_value=mock_resp):
        chunks = list(analyze_image(str(png_file)))

    texts = [c["content"] for c in chunks if c["type"] == "text"]
    assert "A " in texts
    assert "button" in texts
    assert any(c["type"] == "done" for c in chunks)


def test_analyze_with_custom_prompt(png_file: Path):
    """Custom prompt is passed to the Ollama API."""
    captured = {}

    def fake_stream(method, url, **kw):
        captured.update(kw)
        mock = MagicMock()
        mock.status_code = 200
        mock.iter_lines.return_value = iter([
            json.dumps({"done": True}),
        ])
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    with patch("maggy.services.vision.httpx.stream",
               side_effect=fake_stream):
        list(analyze_image(str(png_file), "What color?"))

    body = captured.get("json", {})
    msg = body.get("messages", [{}])[0]
    assert "What color?" in msg.get("content", "")


def test_analyze_ollama_down(png_file: Path):
    """Connection error yields error chunk."""
    import httpx
    with patch("maggy.services.vision.httpx.stream",
               side_effect=httpx.ConnectError("refused")):
        chunks = list(analyze_image(str(png_file)))
    assert any(c["type"] == "error" for c in chunks)
    err = next(c for c in chunks if c["type"] == "error")
    assert "refused" in err["content"].lower() or "connect" in err["content"].lower()


class TestExtractImagePath:
    """Image path detection from chat messages."""

    def test_detects_png_path(self, png_file: Path):
        result = extract_image_path(f"{png_file} review this")
        assert result is not None
        assert result[0] == str(png_file)
        assert result[1] == "review this"

    def test_detects_path_with_prompt(self, png_file: Path):
        msg = f"can u review {png_file} for UI issues"
        result = extract_image_path(msg)
        assert result is not None
        assert result[1] == "can u review for UI issues"

    def test_no_image_returns_none(self):
        assert extract_image_path("fix the bug") is None

    def test_nonexistent_file_returns_none(self):
        assert extract_image_path("/tmp/nope.png") is None

    def test_escaped_spaces(self, tmp_path: Path):
        d = tmp_path / "My Screenshots"
        d.mkdir()
        img = d / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        result = extract_image_path(str(img) + " describe")
        assert result is not None

    def test_tilde_path(self, tmp_path: Path, monkeypatch):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        result = extract_image_path(str(img) + " check")
        assert result is not None
