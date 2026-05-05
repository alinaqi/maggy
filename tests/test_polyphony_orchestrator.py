"""Tests for Polyphony orchestrator (§4 supervisor loop)."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from polyphony.orchestrator import (
    Orchestrator,
    discover_tasks,
    claim_task,
    provision_workspace,
    run_agent,
    verify_result,
)
from polyphony.models import (
    Task, AgentProfile, Identity, RunSpec, Result,
)
from polyphony.store import PolyphonyStore


@pytest.fixture
def store(tmp_path):
    s = PolyphonyStore(tmp_path)
    s.init_db()
    return s


@pytest.fixture
def task():
    return Task(
        title="Fix auth bug",
        source="local",
        source_ref="local",
        task_type="bugfix",
        risk="medium",
    )


@pytest.fixture
def agents():
    return [
        AgentProfile(
            name="claude-opus",
            agent_type="claude",
            cli_command="claude -p",
            strengths=["long_context"],
        ),
    ]


@pytest.fixture
def policy():
    return {
        "rules": [],
        "default": {
            "agent": "claude-opus",
            "fallback": [],
        },
    }


@pytest.fixture
def identities():
    return [
        Identity(
            name="protaige",
            volumes={"claude": "~/.claude"},
        ),
    ]


class TestDiscoverTasks:
    def test_returns_tasks(self, store, task):
        store.save_task(task)
        found = discover_tasks(store)
        assert len(found) == 1
        assert found[0].id == task.id

    def test_empty_store(self, store):
        assert discover_tasks(store) == []


class TestClaimTask:
    def test_transitions_to_claimed(self, store, task):
        store.save_task(task)
        claimed = claim_task(task, store)
        assert claimed.state == "claimed"

    def test_updates_store(self, store, task):
        store.save_task(task)
        claim_task(task, store)
        stored = store.get_task(task.id)
        assert stored.state == "claimed"


class TestProvisionWorkspace:
    @patch("polyphony.orchestrator._create_ws")
    def test_returns_path(self, mock_ws, tmp_path, task):
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        mock_ws.return_value = ws_path
        result = provision_workspace(task, tmp_path, "main")
        assert result == ws_path

    @patch("polyphony.orchestrator._create_ws")
    def test_calls_create(self, mock_ws, tmp_path, task):
        mock_ws.return_value = tmp_path
        provision_workspace(task, tmp_path, "main")
        assert mock_ws.called


class TestRunAgent:
    @patch("polyphony.orchestrator._execute_container")
    def test_returns_result(self, mock_exec, task):
        mock_exec.return_value = Result(
            task_id=task.id,
            run_spec_id="rs-1",
            agent="claude-opus",
            status="succeeded",
        )
        run_spec = RunSpec(
            task_id=task.id,
            agent="claude-opus",
            identity="protaige",
            workspace="/ws",
            image="polyphony-worker:latest",
        )
        result = run_agent(run_spec)
        assert result.status == "succeeded"

    @patch("polyphony.orchestrator._execute_container")
    def test_handles_failure(self, mock_exec, task):
        mock_exec.return_value = Result(
            task_id=task.id,
            run_spec_id="rs-1",
            agent="claude-opus",
            status="failed",
        )
        run_spec = RunSpec(
            task_id=task.id,
            agent="claude-opus",
            identity="protaige",
            workspace="/ws",
            image="polyphony-worker:latest",
        )
        result = run_agent(run_spec)
        assert result.status == "failed"


class TestVerifyResult:
    def test_succeeded_passes(self):
        result = Result(
            task_id="T-1",
            run_spec_id="rs-1",
            agent="claude-opus",
            status="succeeded",
        )
        assert verify_result(result) is True

    def test_failed_fails(self):
        result = Result(
            task_id="T-1",
            run_spec_id="rs-1",
            agent="claude-opus",
            status="failed",
        )
        assert verify_result(result) is False


class TestOrchestrator:
    def test_init(self, store, agents, policy, identities):
        orch = Orchestrator(
            store=store,
            agents=agents,
            policy=policy,
            identities=identities,
        )
        assert orch is not None

    def test_has_step(self, store, agents, policy, identities):
        orch = Orchestrator(
            store=store,
            agents=agents,
            policy=policy,
            identities=identities,
        )
        assert hasattr(orch, "step")
