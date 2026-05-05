"""Tests for Polyphony config loading (§11)."""

import pytest
from polyphony.config import (
    load_config,
    load_identities,
    load_agents,
    load_routing,
    default_config_dir,
)
from polyphony.models import Identity, AgentProfile


class TestDefaultConfigDir:
    def test_returns_path(self):
        d = default_config_dir()
        assert str(d).endswith(".polyphony")


class TestLoadConfig:
    def test_missing_dir_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent")
        assert "workspace_root" in cfg
        assert "poll_interval" in cfg
        assert "max_concurrent_agents" in cfg

    def test_loads_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "workspace_root: /custom/path\n"
            "max_concurrent_agents: 4\n"
        )
        cfg = load_config(tmp_path)
        assert cfg["workspace_root"] == "/custom/path"
        assert cfg["max_concurrent_agents"] == 4

    def test_defaults_fill_missing_keys(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("workspace_root: /x\n")
        cfg = load_config(tmp_path)
        assert "poll_interval" in cfg


class TestLoadIdentities:
    def test_missing_file_returns_empty(self, tmp_path):
        ids = load_identities(tmp_path)
        assert ids == []

    def test_loads_identities(self, tmp_path):
        f = tmp_path / "identities.yaml"
        f.write_text(
            "identities:\n"
            "  - name: test\n"
            "    volumes:\n"
            "      claude: ~/.claude\n"
        )
        ids = load_identities(tmp_path)
        assert len(ids) == 1
        assert isinstance(ids[0], Identity)
        assert ids[0].name == "test"
        assert ids[0].volumes["claude"] == "~/.claude"


class TestLoadAgents:
    def test_missing_file_returns_empty(self, tmp_path):
        agents = load_agents(tmp_path)
        assert agents == []

    def test_loads_agents(self, tmp_path):
        f = tmp_path / "agents.yaml"
        f.write_text(
            "agents:\n"
            "  - name: claude-opus\n"
            "    agent_type: claude\n"
            "    cli_command: claude -p\n"
        )
        agents = load_agents(tmp_path)
        assert len(agents) == 1
        assert isinstance(agents[0], AgentProfile)
        assert agents[0].name == "claude-opus"


class TestLoadRouting:
    def test_missing_file_returns_defaults(self, tmp_path):
        r = load_routing(tmp_path)
        assert "rules" in r
        assert "default" in r

    def test_loads_routing(self, tmp_path):
        f = tmp_path / "routing.yaml"
        f.write_text(
            "rules:\n"
            "  - match: {task_type: bugfix}\n"
            "    agent: kimi\n"
            "default:\n"
            "  agent: claude\n"
        )
        r = load_routing(tmp_path)
        assert len(r["rules"]) == 1
        assert r["default"]["agent"] == "claude"
