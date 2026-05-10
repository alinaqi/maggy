"""Tests for Event Spine — header, typed events, emitter, store."""

from __future__ import annotations

from pathlib import Path

from maggy.event_spine.emitter import EventEmitter
from maggy.event_spine.events import (
    EVENT_TYPES,
    ExecutionEvent,
    IntentEvent,
    MeshEvent,
    OutcomeEvent,
)
from maggy.event_spine.header import EventHeader
from maggy.event_spine.store import EventStore


class TestEventHeader:
    def test_defaults(self):
        h = EventHeader(event_type="intent")
        assert h.event_type == "intent"
        assert h.event_id  # uuid generated
        assert h.timestamp  # iso time generated
        assert h.schema_version == 1
        assert h.confidence == 1.0

    def test_custom_fields(self):
        h = EventHeader(
            event_type="execution",
            task_id="t1",
            project_id="p1",
            agent_id="a1",
        )
        assert h.task_id == "t1"
        assert h.project_id == "p1"


class TestTypedEvents:
    def test_all_eight_types(self):
        assert len(EVENT_TYPES) == 8

    def test_intent_event(self):
        e = IntentEvent(
            intent_text="Add login button",
            decomposed_steps=["create component", "add route"],
        )
        assert e.header.event_type == "intent"
        assert len(e.decomposed_steps) == 2

    def test_execution_event(self):
        e = ExecutionEvent(
            tool_name="grep",
            duration_ms=150,
            success=True,
        )
        assert e.header.event_type == "execution"
        assert e.duration_ms == 150

    def test_outcome_event(self):
        e = OutcomeEvent(success=True, reward=0.9)
        assert e.header.event_type == "outcome"
        assert e.reward == 0.9


class TestEventStore:
    def test_write_and_query(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        h = EventHeader(event_type="intent", task_id="t1")
        store.write(h, {"header": {"event_type": "intent"}, "text": "hi"})
        results = store.query(task_id="t1")
        assert len(results) == 1

    def test_query_by_type(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        h1 = EventHeader(event_type="intent", task_id="t1")
        h2 = EventHeader(event_type="execution", task_id="t1")
        store.write(h1, {"type": "intent"})
        store.write(h2, {"type": "execution"})
        results = store.query(event_type="intent")
        assert len(results) == 1

    def test_count(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        for i in range(5):
            h = EventHeader(
                event_type="execution", task_id=f"t{i}",
            )
            store.write(h, {"i": i})
        assert store.count(event_type="execution") == 5
        assert store.count(event_type="intent") == 0

    def test_limit(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        for i in range(10):
            h = EventHeader(event_type="intent", task_id="t1")
            store.write(h, {"i": i})
        results = store.query(task_id="t1", limit=3)
        assert len(results) == 3


class TestEventEmitter:
    def test_emit_returns_id(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)
        event = IntentEvent(intent_text="test")
        eid = emitter.emit(event)
        assert eid == event.header.event_id

    def test_emit_invalid_raises(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)
        import pytest
        with pytest.raises(ValueError):
            emitter.emit({"not": "an event"})

    def test_trace(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)
        e1 = IntentEvent(intent_text="step 1")
        e1.header.task_id = "task-abc"
        e2 = ExecutionEvent(tool_name="grep")
        e2.header.task_id = "task-abc"
        emitter.emit(e1)
        emitter.emit(e2)
        trace = emitter.trace("task-abc")
        assert len(trace) == 2

    def test_count(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)
        for _ in range(3):
            emitter.emit(IntentEvent(intent_text="x"))
        assert emitter.count(event_type="intent") == 3

    def test_query_by_project(self, tmp_path: Path):
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)
        e = IntentEvent(intent_text="x")
        e.header.project_id = "proj-1"
        emitter.emit(e)
        results = emitter.query(project_id="proj-1")
        assert len(results) == 1
