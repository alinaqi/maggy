"""Tests for Polyphony agent adapters (§8.1-8.3)."""

import pytest
from polyphony.adapters import get_adapter, list_adapters
from polyphony.adapters.claude import ClaudeAdapter
from polyphony.adapters.codex import CodexAdapter
from polyphony.adapters.kimi import KimiAdapter
from polyphony.models import AgentProfile, RunSpec


@pytest.fixture
def claude_profile():
    return AgentProfile(
        name="claude-opus",
        agent_type="claude",
        cli_command="claude -p",
        strengths=["long_context"],
        event_protocol="stream-json",
    )


@pytest.fixture
def codex_profile():
    return AgentProfile(
        name="codex-default",
        agent_type="codex",
        cli_command="codex exec",
        strengths=["code"],
        event_protocol="ndjson",
    )


@pytest.fixture
def kimi_profile():
    return AgentProfile(
        name="kimi-default",
        agent_type="kimi",
        cli_command="kimi --print -y",
        strengths=["code"],
        event_protocol="ndjson",
    )


@pytest.fixture
def run_spec():
    return RunSpec(
        task_id="T-1",
        agent="claude-opus",
        identity="protaige",
        workspace="/workspace",
        image="polyphony-worker:latest",
        max_turns=10,
        env_overlay={"ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY"},
        volume_mounts=["~/.claude:/home/worker/.claude:ro"],
    )


class TestRegistry:
    def test_list_adapters(self):
        names = list_adapters()
        assert "claude" in names
        assert "codex" in names
        assert "kimi" in names

    def test_get_claude_adapter(self):
        adapter = get_adapter("claude")
        assert isinstance(adapter, ClaudeAdapter)

    def test_get_codex_adapter(self):
        adapter = get_adapter("codex")
        assert isinstance(adapter, CodexAdapter)

    def test_get_kimi_adapter(self):
        adapter = get_adapter("kimi")
        assert isinstance(adapter, KimiAdapter)

    def test_unknown_adapter_raises(self):
        with pytest.raises(KeyError, match="gemini"):
            get_adapter("gemini")


class TestClaudeAdapter:
    def test_build_command(self, claude_profile, run_spec):
        adapter = ClaudeAdapter()
        cmd = adapter.build_command(claude_profile, run_spec)
        assert "claude" in cmd[0]
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd

    def test_prompt_included(self, claude_profile, run_spec):
        adapter = ClaudeAdapter()
        run_spec.env_overlay["PROMPT"] = "Fix the bug"
        cmd = adapter.build_command(claude_profile, run_spec)
        cmd_str = " ".join(cmd)
        assert "claude" in cmd_str

    def test_detect_completion(self):
        adapter = ClaudeAdapter()
        assert adapter.detect_completion({"type": "result"}) is True
        assert adapter.detect_completion({"type": "message"}) is False

    def test_detect_quota(self):
        adapter = ClaudeAdapter()
        assert adapter.detect_quota("rate limit exceeded") is True
        assert adapter.detect_quota("all good") is False


class TestCodexAdapter:
    def test_build_command(self, codex_profile, run_spec):
        adapter = CodexAdapter()
        cmd = adapter.build_command(codex_profile, run_spec)
        assert "codex" in cmd[0]
        assert "exec" in cmd
        assert "--full-auto" in cmd

    def test_detect_completion(self):
        adapter = CodexAdapter()
        assert adapter.detect_completion({"status": "completed"}) is True
        assert adapter.detect_completion({"status": "running"}) is False

    def test_detect_quota(self):
        adapter = CodexAdapter()
        assert adapter.detect_quota("quota exceeded") is True
        assert adapter.detect_quota("running") is False


class TestKimiAdapter:
    def test_build_command(self, kimi_profile, run_spec):
        adapter = KimiAdapter()
        cmd = adapter.build_command(kimi_profile, run_spec)
        assert "kimi" in cmd[0]
        assert "--print" in cmd
        assert "-y" in cmd

    def test_detect_completion(self):
        adapter = KimiAdapter()
        assert adapter.detect_completion({"done": True}) is True
        assert adapter.detect_completion({"done": False}) is False

    def test_detect_quota(self):
        adapter = KimiAdapter()
        assert adapter.detect_quota("rate limit") is True
        assert adapter.detect_quota("ok") is False
