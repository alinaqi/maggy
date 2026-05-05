"""Tests for Polyphony SQLite store."""

import pytest
from polyphony.models import Task, RunSpec, Result
from polyphony.store import PolyphonyStore


@pytest.fixture
def store(tmp_path):
    s = PolyphonyStore(tmp_path)
    s.init_db()
    return s


@pytest.fixture
def sample_task():
    return Task(
        title="Fix bug",
        source="github",
        source_ref="owner/repo#1",
    )


class TestInit:
    def test_creates_db(self, tmp_path):
        s = PolyphonyStore(tmp_path)
        s.init_db()
        assert (tmp_path / "orchestrator.db").exists()

    def test_creates_gitignore(self, tmp_path):
        s = PolyphonyStore(tmp_path)
        s.init_db()
        gi = tmp_path / ".gitignore"
        assert gi.exists()
        assert "*" in gi.read_text()

    def test_idempotent(self, tmp_path):
        s = PolyphonyStore(tmp_path)
        s.init_db()
        s.init_db()  # no error


class TestTaskCRUD:
    def test_save_and_get(self, store, sample_task):
        store.save_task(sample_task)
        loaded = store.get_task(sample_task.id)
        assert loaded is not None
        assert loaded.title == "Fix bug"
        assert loaded.source == "github"

    def test_get_missing_returns_none(self, store):
        assert store.get_task("nonexistent") is None

    def test_list_tasks(self, store):
        t1 = Task(title="A", source="local", source_ref="1")
        t2 = Task(title="B", source="local", source_ref="2")
        store.save_task(t1)
        store.save_task(t2)
        tasks = store.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_state(self, store, sample_task):
        store.save_task(sample_task)
        found = store.list_tasks(state="discovered")
        assert len(found) == 1
        empty = store.list_tasks(state="running")
        assert len(empty) == 0

    def test_update_task(self, store, sample_task):
        store.save_task(sample_task)
        sample_task.state = "claimed"
        store.save_task(sample_task)
        loaded = store.get_task(sample_task.id)
        assert loaded.state == "claimed"


class TestRunSpecCRUD:
    def test_save_and_get(self, store):
        rs = RunSpec(
            task_id="t1",
            agent="claude",
            identity="protaige",
            workspace="/tmp/ws",
            image="img:latest",
        )
        store.save_run_spec(rs)
        loaded = store.get_run_spec(rs.id)
        assert loaded is not None
        assert loaded.agent == "claude"

    def test_get_missing(self, store):
        assert store.get_run_spec("nope") is None


class TestResultCRUD:
    def test_save_and_get(self, store):
        r = Result(
            task_id="t1",
            run_spec_id="rs1",
            agent="claude",
            status="succeeded",
        )
        store.save_result(r)
        loaded = store.get_result(r.id)
        assert loaded is not None
        assert loaded.status == "succeeded"

    def test_list_results_by_task(self, store):
        r1 = Result(
            task_id="t1",
            run_spec_id="rs1",
            agent="claude",
            status="failed",
        )
        r2 = Result(
            task_id="t1",
            run_spec_id="rs2",
            agent="kimi",
            status="succeeded",
        )
        store.save_result(r1)
        store.save_result(r2)
        results = store.list_results(task_id="t1")
        assert len(results) == 2


class TestStateLog:
    def test_log_transition(self, store, sample_task):
        store.save_task(sample_task)
        store.log_transition(
            sample_task.id, "discovered", "claimed",
        )
        log = store.get_state_log(sample_task.id)
        assert len(log) == 1
        assert log[0]["from_state"] == "discovered"
        assert log[0]["to_state"] == "claimed"
