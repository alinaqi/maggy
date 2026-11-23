"""Profiles and loaders for worker launch-policy tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from maggy.harness.schema import HarnessProfile
from maggy.worker.adapter_loader import load_adapters
from maggy.worker.adapter_spec import AdapterSpec

SHIPPED = ["claude", "codex", "opencode", "pi"]
GOLDEN = Path(__file__).parent / "fixtures" / "worker_launch" / "golden.yaml"
PROFILES = {
    "read_only": {"write": False, "network": False, "shell": False},
    "workspace": {"write": "workspace", "network": "registries", "shell": "allowlist"},
    "shell_only": {"write": False, "network": False, "shell": True},
}


def profile(allow_host: bool = False, isolation: str = "worktree") -> HarnessProfile:
    return HarnessProfile.model_validate({
        "permissions": {"profiles": PROFILES},
        "worker": {"allow_host_execution": allow_host, "isolation": isolation},
    })


def shipped(name: str) -> AdapterSpec:
    return load_adapters(user_dir=Path("/nonexistent"))[name]


def golden() -> dict:
    return yaml.safe_load(GOLDEN.read_text())
