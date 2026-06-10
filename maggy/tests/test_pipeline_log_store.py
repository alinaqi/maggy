"""Tests for pipeline log store."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from maggy.pipeline.log_store import PipelineLogStore
from maggy.pipeline.models import PipelineContext, PipelineResult


@pytest.fixture
def store(tmp_path):
    return PipelineLogStore(tmp_path / "test_pipeline.db")


def _ctx(session_id="sess1", message="hello world"):
    return PipelineContext(
        session_id=session_id, message=message,
        project_key="proj", working_dir="/tmp",
    )


def _result(model="claude", success=True, cost=0.03, **kw):
    defaults = dict(
        backend="claude", blast=5, task_type="general",
        reason="default", latency_ms=1200.0,
        cost_usd=cost, tokens_in=500, tokens_out=200,
    )
    defaults.update(kw)
    return PipelineResult(model=model, success=success, **defaults)


class TestRecord:
    def test_inserts_row(self, store):
        store.record(_result(), _ctx())
        rows = store.recent(limit=10)
        assert len(rows) == 1

    def test_truncates_message(self, store):
        long_msg = "x" * 300
        store.record(_result(), _ctx(message=long_msg))
        rows = store.recent(limit=1)
        assert len(rows[0]["message_snippet"]) == 120

    def test_stores_all_fields(self, store):
        store.record(
            _result(model="kimi", cost=0.001, error="boom", fallback_used="claude"),
            _ctx(session_id="s99"),
        )
        row = store.recent(limit=1)[0]
        assert row["model"] == "kimi"
        assert row["session_id"] == "s99"
        assert row["cost_usd"] == 0.001
        assert row["error"] == "boom"
        assert row["fallback_used"] == "claude"


class TestRecent:
    def test_limit(self, store):
        for i in range(10):
            store.record(_result(), _ctx(session_id=f"s{i}"))
        assert len(store.recent(limit=3)) == 3

    def test_filter_by_session(self, store):
        store.record(_result(), _ctx(session_id="a"))
        store.record(_result(), _ctx(session_id="b"))
        rows = store.recent(session_id="a")
        assert len(rows) == 1
        assert rows[0]["session_id"] == "a"

    def test_filter_by_model(self, store):
        store.record(_result(model="claude"), _ctx())
        store.record(_result(model="kimi"), _ctx())
        rows = store.recent(model="kimi")
        assert len(rows) == 1
        assert rows[0]["model"] == "kimi"

    def test_ordered_newest_first(self, store):
        store.record(_result(model="first"), _ctx())
        store.record(_result(model="second"), _ctx())
        rows = store.recent(limit=10)
        assert rows[0]["model"] == "second"

    def test_empty(self, store):
        assert store.recent() == []


class TestStats:
    def test_basic_stats(self, store):
        store.record(_result(cost=0.01, success=True), _ctx())
        store.record(_result(cost=0.02, success=True), _ctx())
        store.record(
            _result(cost=0.0, success=False, error="fail"), _ctx(),
        )
        s = store.stats("all")
        assert s["total_calls"] == 3
        assert s["total_cost"] == pytest.approx(0.03)
        assert s["success_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_by_model(self, store):
        store.record(_result(model="claude"), _ctx())
        store.record(_result(model="kimi"), _ctx())
        store.record(_result(model="kimi"), _ctx())
        s = store.stats("all")
        by_model = {m["model"]: m for m in s["by_model"]}
        assert by_model["kimi"]["calls"] == 2
        assert by_model["claude"]["calls"] == 1

    def test_empty_stats(self, store):
        s = store.stats("all")
        assert s["total_calls"] == 0
        assert s["success_rate"] == 0.0
