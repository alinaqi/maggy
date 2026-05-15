"""Tests for Event Spine — header, events, emitter, store."""

import pytest
from pathlib import Path

from maggy.event_spine.header import EventHeader
from maggy.event_spine.events import (
    IntentEvent, BindingEvent, ExecutionEvent,
    MemoryEvent, PersistenceEvent, OutcomeEvent,
    MutationEvent, MeshEvent, EVENT_TYPES,
)
from maggy.event_spine.emitter import EventEmitter
from maggy.event_spine.store import EventStore


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    return EventStore(tmp_path / "events.db")


@pytest.fixture
def emitter(store: EventStore) -> EventEmitter:
    return EventEmitter(store)


class TestEventHeader:
    def test_defaults(self):
        h = EventHeader(event_type="test")
        assert h.event_type == "test"
        assert h.event_id  # auto-generated
        assert h.timestamp  # auto-generated
        assert h.schema_version == 1

    def test_custom_fields(self):
        h = EventHeader(
            event_type="intent",
            task_id="t1", project_id="p1",
            model_id="claude", confidence=0.9,
        )
        assert h.task_id == "t1"
        assert h.confidence == 0.9


class TestTypedEvents:
    def test_all_8_types(self):
        assert len(EVENT_TYPES) == 8

    def test_intent_event(self):
        e = IntentEvent(intent_text="fix auth bug")
        assert e.header.event_type == "intent"
        assert e.intent_text == "fix auth bug"

    def test_binding_event(self):
        e = BindingEvent(
            phrase="deploy", selected_tool="vercel",
            candidates=["vercel", "netlify"],
        )
        assert e.header.event_type == "binding"
        assert len(e.candidates) == 2

    def test_execution_event(self):
        e = ExecutionEvent(
            tool_name="grep", duration_ms=50, success=True,
        )
        assert e.duration_ms == 50

    def test_outcome_event(self):
        e = OutcomeEvent(success=True, reward=0.8)
        assert e.reward == 0.8


class TestEventEmitter:
    def test_emit_returns_id(self, emitter):
        e = IntentEvent(intent_text="test")
        eid = emitter.emit(e)
        assert eid == e.header.event_id

    def test_emit_invalid(self, emitter):
        with pytest.raises(ValueError):
            emitter.emit({"not": "an event"})

    def test_query_by_task(self, emitter):
        e1 = IntentEvent(intent_text="task A")
        e1.header.task_id = "t1"
        e2 = IntentEvent(intent_text="task B")
        e2.header.task_id = "t2"
        emitter.emit(e1)
        emitter.emit(e2)
        results = emitter.query(task_id="t1")
        assert len(results) == 1

    def test_query_by_type(self, emitter):
        emitter.emit(IntentEvent(intent_text="x"))
        emitter.emit(BindingEvent(phrase="y"))
        results = emitter.query(event_type="intent")
        assert len(results) == 1

    def test_trace(self, emitter):
        for i in range(3):
            e = ExecutionEvent(tool_name=f"tool_{i}")
            e.header.task_id = "task_x"
            emitter.emit(e)
        trace = emitter.trace("task_x")
        assert len(trace) == 3

    def test_count(self, emitter):
        emitter.emit(IntentEvent(intent_text="a"))
        emitter.emit(IntentEvent(intent_text="b"))
        assert emitter.count(event_type="intent") == 2
        assert emitter.count() == 2


class TestEventStore:
    def test_archive_no_old_events(self, store, tmp_path):
        archived = store.archive_old(
            days=90, archive_dir=tmp_path / "archive",
        )
        assert archived == 0

    def test_write_and_query(self, store):
        h = EventHeader(event_type="test", task_id="t1")
        store.write(h, {"header": {}, "data": "value"})
        results = store.query(task_id="t1")
        assert len(results) == 1

    def test_count(self, store):
        h = EventHeader(event_type="test")
        store.write(h, {"header": {}})
        assert store.count() == 1
        assert store.count(event_type="test") == 1
        assert store.count(event_type="other") == 0
