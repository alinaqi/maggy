"""PiAdapter use of cli_discovery, incl. skip-permission flags (still consumed by the executor)."""

from __future__ import annotations

import pytest
from cli_discovery_helpers import fake_clis  # noqa: F401  (autouse fixture)

from maggy.adapters.cli_discovery import discover_cli

# PiAdapter (and so the executor, via send_with_fallback) builds the command for
# models without a pinned manifest (claude, codex, gpt) from the discovered
# profile. Headless runs rely on the skip-permission flag discovery provides;
# dropping it is an executor behaviour change outside the approved scope.
_EXPECTED_AUTO_APPROVE = {
    "claude": "--dangerously-skip-permissions",
    "codex": "--dangerously-bypass-approvals-and-sandbox",
    "kimi": "--yolo",
}


@pytest.mark.parametrize("name", sorted(_EXPECTED_AUTO_APPROVE))
def test_discovered_auto_approve_flag(name):
    p = discover_cli(name)
    assert p.auto_approve_flag == _EXPECTED_AUTO_APPROVE[name]
    cmd = p.build_command("do stuff", "/tmp/repo", 5)
    assert _EXPECTED_AUTO_APPROVE[name] in cmd


@pytest.mark.parametrize("model_name", ["claude", "codex", "gpt"])
def test_pi_adapter_unpinned_models_keep_permission_flag(model_name):
    from maggy.adapters.cli_manifests import pinned_command
    from maggy.adapters.pi import PiAdapter
    pi = PiAdapter()
    model = pi.get_model(model_name)
    assert pinned_command(model, "hi", "/tmp", 5) is None
    cmd = pi._build_command(model, "hi", 5, "/tmp")
    assert _EXPECTED_AUTO_APPROVE[model.cli_command] in cmd


def test_cli_models_route_reports_auto_approve():
    import asyncio

    from maggy.api.routes_setup import cli_models
    body = asyncio.run(cli_models())
    claude = next(p for p in body["profiles"] if p["name"] == "claude")
    assert claude["auto_approve"] == "--dangerously-skip-permissions"


def test_pi_adapter_uses_discovery():
    from maggy.adapters.pi import PiAdapter
    pi = PiAdapter()
    profiles = pi.discovered_profiles
    assert "claude" in profiles
    assert profiles["claude"].installed is True
    assert "ollama" in profiles
    assert profiles["ollama"].installed is True
