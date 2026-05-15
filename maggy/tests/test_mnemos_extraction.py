"""Tests for tool → node extraction pipeline."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.extraction import (
    classify_signal,
    detect_working_sequences,
    extract_node_from_signal,
    extract_working_node,
    run_extraction,
)
from maggy.mnemos.signals import ToolSignal


def _sig(
    tool: str = "Read",
    path: str = "src/a.py",
) -> ToolSignal:
    return ToolSignal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_name=tool,
        file_path=path,
    )


class TestClassifySignal:
    def test_read_is_context(self):
        assert classify_signal(_sig("Read")) == "ContextNode"

    def test_write_is_result(self):
        assert classify_signal(_sig("Write")) == "ResultNode"

    def test_unknown_is_none(self):
        assert classify_signal(_sig("CustomTool")) is None


class TestExtractNode:
    def test_creates_node(self):
        node = extract_node_from_signal(_sig("Read", "src/foo.py"), "t1")
        assert node is not None
        assert node.type == "ContextNode"
        assert "src" in node.scope_tags

    def test_none_for_unknown(self):
        assert extract_node_from_signal(_sig("X"), "t1") is None


class TestWorkingSequences:
    def test_groups_same_dir(self):
        sigs = [_sig(path="src/a.py"), _sig(path="src/b.py")]
        seqs = detect_working_sequences(sigs)
        assert len(seqs) == 1

    def test_empty_input(self):
        assert detect_working_sequences([]) == []

    def test_creates_working_node(self):
        sigs = [_sig("Read"), _sig("Write")]
        wn = extract_working_node(sigs, "t1")
        assert wn.type == "WorkingNode"
        assert "Read" in wn.content


class TestRunExtraction:
    def test_full_pipeline(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        sigs = [
            _sig("Read", "src/a.py"),
            _sig("Write", "src/b.py"),
        ]
        created = run_extraction(sigs, "t1", db)
        assert len(created) >= 2

    def test_dedup_context_nodes(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        sigs = [
            _sig("Read", "src/a.py"),
            _sig("Read", "src/a.py"),
        ]
        created = run_extraction(sigs, "t1", db)
        context = [n for n in created if n.type == "ContextNode"]
        assert len(context) == 1
