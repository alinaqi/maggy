"""Tests for Polyphony data models (§3 of spec)."""

import pytest
from polyphony.models import (
    TASK_TYPES,
    RISK_LEVELS,
    SCOPES,
    Task,
    Identity,
    AgentProfile,
    RunSpec,
    Result,
    _now,
    _uuid,
)


class TestHelpers:
    def test_now_returns_iso_string(self):
        ts = _now()
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_uuid_returns_unique(self):
        a, b = _uuid(), _uuid()
        assert a != b
        assert len(a) == 36


class TestTaskConstants:
    def test_task_types(self):
        expected = {
            "research", "bugfix", "feature",
            "refactor", "migration", "docs", "review",
        }
        assert set(TASK_TYPES) == expected

    def test_risk_levels(self):
        assert set(RISK_LEVELS) == {"low", "medium", "high"}

    def test_scopes(self):
        expected = {
            "single_file", "single_module",
            "multi_module", "multi_repo",
        }
        assert set(SCOPES) == expected


class TestTask:
    def test_create_minimal(self):
        t = Task(
            title="Fix login bug",
            source="github",
            source_ref="owner/repo#42",
        )
        assert t.title == "Fix login bug"
        assert t.source == "github"
        assert len(t.id) == 36
        assert t.state == "discovered"
        assert t.task_type == "feature"
        assert t.risk == "low"

    def test_defaults(self):
        t = Task(title="x", source="local", source_ref="1")
        assert t.scope == []
        assert t.context_tokens == 0
        assert t.requires_web is False
        assert t.run_spec_id is None
        assert t.metadata == {}

    def test_to_dict(self):
        t = Task(title="x", source="local", source_ref="1")
        d = t.to_dict()
        assert d["title"] == "x"
        assert "id" in d
        assert "created_at" in d


class TestIdentity:
    def test_create(self):
        i = Identity(
            name="protaige",
            volumes={"claude": "~/.claude"},
        )
        assert i.name == "protaige"
        assert i.volumes["claude"] == "~/.claude"
        assert i.api_keys == {}
        assert i.cost_ceiling_usd_per_day is None

    def test_with_api_keys(self):
        i = Identity(
            name="test",
            volumes={},
            api_keys={"anthropic": "ANTHROPIC_API_KEY"},
        )
        assert i.api_keys["anthropic"] == "ANTHROPIC_API_KEY"


class TestAgentProfile:
    def test_create(self):
        a = AgentProfile(
            name="claude-opus",
            agent_type="claude",
            cli_command="claude -p",
        )
        assert a.name == "claude-opus"
        assert a.context_window_tokens == 200000
        assert a.strengths == []

    def test_event_protocol_default(self):
        a = AgentProfile(
            name="x",
            agent_type="claude",
            cli_command="claude -p",
        )
        assert a.event_protocol == "ndjson"


class TestRunSpec:
    def test_create(self):
        r = RunSpec(
            task_id="t1",
            agent="claude-opus",
            identity="protaige",
            workspace="/tmp/ws",
            image="polyphony/claude:latest",
        )
        assert r.task_id == "t1"
        assert r.attempt == 1
        assert r.max_turns == 25
        assert r.deadline_seconds == 1800
        assert r.allowed_paths == []
        assert r.proof_of_work == []

    def test_immutable_concept(self):
        """RunSpec fields have defaults; verify they're set."""
        r = RunSpec(
            task_id="t1",
            agent="x",
            identity="y",
            workspace="/w",
            image="img",
        )
        assert len(r.id) == 36


class TestResult:
    def test_create(self):
        r = Result(
            task_id="t1",
            run_spec_id="rs1",
            agent="claude-opus",
            status="succeeded",
        )
        assert r.status == "succeeded"
        assert r.turns == 0
        assert r.duration_seconds == 0
        assert r.cost_usd is None
        assert r.events == []
        assert r.artifacts == {}

    def test_status_values(self):
        for s in ("succeeded", "failed", "quota", "timeout", "crash"):
            r = Result(
                task_id="t",
                run_spec_id="r",
                agent="a",
                status=s,
            )
            assert r.status == s
