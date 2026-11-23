"""Contract tests for the shipped adapters: flags vs --help, golden argv, AWG off."""

from __future__ import annotations

import json
import re

import pytest

from maggy.worker.launch import resolve_launch
from maggy.worker.templating import ArgvValues
from worker_fixture_helpers import FIXTURES, load_meta
from worker_launch_helpers import SHIPPED, golden, profile, shipped

CASES = [(name, perm) for name in SHIPPED for perm in ("read_only", "workspace")]


def _flags(adapter) -> set[str]:
    lists = [adapter.argv, adapter.model_flags, adapter.disable_awg.flags,
             *adapter.permissions.values()]
    return {item for items in lists for item in items if item.startswith("-")}


@pytest.mark.parametrize("name", SHIPPED)
def test_adapter_version_matches_recorded_help(name):
    adapter, meta = shipped(name), load_meta(name)
    help_text = (FIXTURES / name / meta["help"]).read_text()
    assert adapter.tested_version and adapter.tested_version in meta["version"]
    assert adapter.tested_version in help_text.splitlines()[0]
    assert adapter.output == meta["parser"]


@pytest.mark.parametrize("name", SHIPPED)
def test_every_adapter_flag_is_in_the_help_fixture(name):
    help_text = (FIXTURES / name / load_meta(name)["help"]).read_text()
    for flag in _flags(shipped(name)):
        assert re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text), flag


@pytest.mark.parametrize(("name", "perm"), CASES)
def test_launch_matches_golden(name, perm):
    data = golden()
    expected = data["launches"][name][perm]
    plan = resolve_launch(shipped(name), profile(allow_host=True), perm)
    values = ArgvValues(permission="ignored", **data["values"])
    assert plan.argv(values) == expected["argv"]
    assert plan.env == expected["env"]
    assert plan.host_execution is expected["host_execution"]


@pytest.mark.parametrize(("name", "perm"), CASES)
def test_launch_always_disables_awg(name, perm):
    adapter = shipped(name)
    plan = resolve_launch(adapter, profile(allow_host=True), perm)
    argv = plan.argv(ArgvValues(prompt="p", workspace="/ws", permission=perm))
    flags = adapter.disable_awg.flags
    assert "{awg_off_flags}" in adapter.argv and (flags or adapter.disable_awg.env)
    assert any(argv[i:i + len(flags)] == flags for i in range(len(argv)))
    assert adapter.disable_awg.env.items() <= plan.env.items()


def _argv(name: str) -> list[str]:
    plan = resolve_launch(shipped(name), profile(), "read_only")
    return plan.argv(ArgvValues(prompt="p", workspace="/ws", permission="read_only"))


def test_claude_awg_off_skips_mcp_config_and_denies_awg_plugin_tools():
    argv = _argv("claude")
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert argv[argv.index("--disallowedTools") + 1] == "mcp__awg"


def test_codex_awg_off_disables_the_awg_mcp_server():
    argv = _argv("codex")
    assert ["-c", "mcp_servers.awg.enabled=false"] == argv[4:6]


def test_opencode_awg_off_disables_plugins_and_awg_mcp():
    plan = resolve_launch(shipped("opencode"), profile(), "read_only")
    assert "--pure" in _argv("opencode")
    config = json.loads(plan.env["OPENCODE_CONFIG_CONTENT"])
    assert config["mcp"]["awg"]["enabled"] is False


def test_pi_awg_off_disables_extension_discovery():
    assert "--no-extensions" in _argv("pi")
