"""Shared fixtures for worker adapter tests."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

VALID_ADAPTER: dict = {
    "name": "fake",
    "tested_version": "1.0.0",
    "version_range": ">=1.0,<2",
    "detect": ["fake", "--version"],
    "argv": ["fake", "-p", "{model_flags}", "{permission_flags}",
             "{awg_off_flags}", "{prompt}"],
    "cwd": "{workspace}",
    "model_flags": ["--model", "{model}"],
    "permissions": {"read_only": ["--read-only"], "workspace": []},
    "sandbox": {"native": False, "notes": "no OS sandbox"},
    "output": "text",
    "instruction_file": "AGENTS.md",
    "quota_patterns": ["rate limit", "429"],
    "env": {"provider_keys": ["FAKE_API_KEY"], "auth_files": ["~/.fake/auth.json"]},
    "disable_awg": {"flags": ["--no-mcp"], "env": {"FAKE_NO_AWG": "1"}},
    "cost": {"streams": False, "fixed_reservation_usd": 0.5},
}


def adapter_data(**changes) -> dict:
    data = copy.deepcopy(VALID_ADAPTER)
    data.update(changes)
    return data


def write_adapter(directory: Path, data: dict, stem: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem or data['name']}.yaml"
    path.write_text(yaml.safe_dump(data))
    return path
