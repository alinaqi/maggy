"""Tests for Polyphony router (§5.2-5.6)."""

import pytest
from polyphony.models import Task, AgentProfile, RunSpec
from polyphony.router import route, select_agent, match_rule


@pytest.fixture
def agents():
    return [
        AgentProfile(
            name="claude-opus",
            agent_type="claude",
            cli_command="claude -p",
            strengths=["long_context", "research"],
        ),
        AgentProfile(
            name="codex-default",
            agent_type="codex",
            cli_command="codex exec",
            strengths=["code"],
        ),
        AgentProfile(
            name="kimi-default",
            agent_type="kimi",
            cli_command="kimi --print -y",
            strengths=["code"],
        ),
    ]


@pytest.fixture
def policy():
    return {
        "rules": [
            {
                "match": {"task_type": "docs", "risk": "low"},
                "agent": "kimi-default",
            },
            {
                "match": {"task_type": "bugfix"},
                "agent": "codex-default",
            },
            {
                "match": {"risk": "high"},
                "agent": "claude-opus",
            },
        ],
        "default": {
            "agent": "claude-opus",
            "fallback": ["codex-default", "kimi-default"],
        },
    }


class TestMatchRule:
    def test_matches_single_field(self):
        task = Task(
            title="x", source="local", source_ref="1",
            task_type="docs",
        )
        rule = {"match": {"task_type": "docs"}}
        assert match_rule(task, rule) is True

    def test_no_match(self):
        task = Task(
            title="x", source="local", source_ref="1",
            task_type="feature",
        )
        rule = {"match": {"task_type": "docs"}}
        assert match_rule(task, rule) is False

    def test_matches_multiple_fields(self):
        task = Task(
            title="x", source="local", source_ref="1",
            task_type="docs", risk="low",
        )
        rule = {"match": {"task_type": "docs", "risk": "low"}}
        assert match_rule(task, rule) is True

    def test_partial_match_fails(self):
        task = Task(
            title="x", source="local", source_ref="1",
            task_type="docs", risk="high",
        )
        rule = {"match": {"task_type": "docs", "risk": "low"}}
        assert match_rule(task, rule) is False


class TestSelectAgent:
    def test_selects_by_rule(self, agents, policy):
        task = Task(
            title="Fix readme", source="local",
            source_ref="1", task_type="docs", risk="low",
        )
        agent = select_agent(task, agents, policy)
        assert agent.name == "kimi-default"

    def test_falls_to_default(self, agents, policy):
        task = Task(
            title="New feature", source="local",
            source_ref="1", task_type="feature", risk="medium",
        )
        agent = select_agent(task, agents, policy)
        assert agent.name == "claude-opus"

    def test_high_risk_matches_claude(self, agents, policy):
        task = Task(
            title="Refactor auth", source="local",
            source_ref="1", task_type="refactor", risk="high",
        )
        agent = select_agent(task, agents, policy)
        assert agent.name == "claude-opus"


class TestRoute:
    def test_returns_run_spec(self, agents, policy):
        task = Task(
            title="Fix bug", source="github",
            source_ref="o/r#1", task_type="bugfix",
        )
        rs = route(task, agents, policy, identity="test")
        assert isinstance(rs, RunSpec)
        assert rs.task_id == task.id
        assert rs.agent == "codex-default"
        assert rs.identity == "test"

    def test_run_spec_has_fallback(self, agents, policy):
        task = Task(
            title="New feature", source="local",
            source_ref="1", task_type="feature",
        )
        rs = route(task, agents, policy, identity="test")
        # default rule has fallback
        assert isinstance(rs.fallback, list)
