"""Tests for blueprint extraction — fingerprint + keyword + template."""
from __future__ import annotations

from unittest.mock import MagicMock

from maggy.blueprint_extract import (
    build_context,
    capture_blueprint,
    extract_keywords,
    extract_template,
    fingerprint,
)


def test_extract_keywords_filters_noise():
    kw = extract_keywords("please can you generate the report")
    assert "please" not in kw
    assert "generate" in kw
    assert "report" in kw


def test_extract_keywords_strips_paths():
    kw = extract_keywords(
        "generate report from /Users/ali/docs/airbus.md"
    )
    assert "ali" not in kw
    assert "docs" not in kw
    assert "generate" in kw
    assert "report" in kw


def test_extract_keywords_short_words():
    kw = extract_keywords("do it ok go run test")
    assert "do" not in kw
    assert "test" in kw
    assert "run" in kw


def test_fingerprint_deterministic():
    a = fingerprint("docs", ["report", "generate"])
    b = fingerprint("docs", ["generate", "report"])
    assert a == b


def test_fingerprint_differs_by_type():
    a = fingerprint("docs", ["report"])
    b = fingerprint("security", ["report"])
    assert a != b


def test_extract_template_paths():
    msg = "process /Users/ali/data/airbus.md and generate report"
    t = extract_template(msg)
    assert "/Users/ali/data/airbus.md" not in t
    assert "{path}" in t


def test_capture_skips_short():
    store = MagicMock()
    capture_blueprint("hi", "general", ["Read x"], "local", store)
    store.record.assert_not_called()


def test_capture_records():
    store = MagicMock()
    capture_blueprint(
        "generate benchmark report for airbus",
        "docs", ["Read src/x", "$ npm run build"],
        "claude", store,
    )
    store.record.assert_called_once()


def test_build_context_formats():
    bp = {
        "tool_sequence": ["Read src/main.py", "$ npm run build"],
        "prompt_template": "generate {path} report",
        "task_type": "docs",
    }
    ctx = build_context(bp)
    assert "Read src/main.py" in ctx
    assert "npm run build" in ctx
