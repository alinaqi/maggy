"""Configuration loading for Polyphony (spec §11)."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import AgentProfile, Identity

DEFAULTS = {
    "workspace_root": "~/polyphony/workspaces",
    "mirror_root": "~/polyphony/mirrors",
    "poll_interval": "30s",
    "max_concurrent_agents": 8,
    "event_idle_timeout": "5m",
}

DEFAULT_ROUTING = {
    "rules": [],
    "default": {
        "agent": "claude",
        "model": "sonnet-4-6",
        "fallback": [],
    },
}


def default_config_dir() -> Path:
    return Path.home() / ".polyphony"


def load_config(config_dir: Path) -> dict:
    """Load config.yaml, merging with defaults."""
    cfg = dict(DEFAULTS)
    path = Path(config_dir) / "config.yaml"
    if path.exists():
        with open(path) as f:
            loaded = yaml.safe_load(f) or {}
        cfg.update(loaded)
    return cfg


def load_identities(config_dir: Path) -> list[Identity]:
    """Load identities.yaml into Identity objects."""
    path = Path(config_dir) / "identities.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return [
        Identity(
            name=item["name"],
            volumes=item.get("volumes", {}),
            api_keys=item.get("api_keys", {}),
            cost_ceiling_usd_per_day=item.get(
                "cost_ceiling_usd_per_day"
            ),
        )
        for item in data.get("identities", [])
    ]


def load_agents(config_dir: Path) -> list[AgentProfile]:
    """Load agents.yaml into AgentProfile objects."""
    path = Path(config_dir) / "agents.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return [
        AgentProfile(
            name=item["name"],
            agent_type=item["agent_type"],
            cli_command=item["cli_command"],
            context_window_tokens=item.get(
                "context_window_tokens", 200000
            ),
            strengths=item.get("strengths", []),
            event_protocol=item.get("event_protocol", "ndjson"),
        )
        for item in data.get("agents", [])
    ]


def load_routing(config_dir: Path) -> dict:
    """Load routing.yaml, merging with defaults."""
    routing = dict(DEFAULT_ROUTING)
    path = Path(config_dir) / "routing.yaml"
    if not path.exists():
        return routing
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if "rules" in data:
        routing["rules"] = data["rules"]
    if "default" in data:
        routing["default"] = data["default"]
    return routing
