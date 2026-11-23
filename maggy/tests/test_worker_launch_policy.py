"""Fail-closed launch policy: host execution, native sandboxes, container isolation."""

from __future__ import annotations

import pytest

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.launch import LaunchPlan, Refused, resolve_launch
from maggy.worker.templating import ArgvValues
from worker_helpers import adapter_data
from worker_launch_helpers import SHIPPED, profile, shipped

NO_SANDBOX = ["opencode", "pi"]
NATIVE = ["claude", "codex"]


@pytest.mark.parametrize("name", SHIPPED)
def test_read_only_runs_on_every_adapter_without_opt_in(name):
    plan = resolve_launch(shipped(name), profile(), "read_only")
    assert isinstance(plan, LaunchPlan) and plan.host_execution is False


@pytest.mark.parametrize("name", NO_SANDBOX)
@pytest.mark.parametrize("perm", ["workspace", "shell_only"])
def test_write_or_shell_without_native_sandbox_is_refused(name, perm):
    adapter = shipped(name) if perm == "workspace" else _with_shell_only(name)
    with pytest.raises(Refused) as info:
        resolve_launch(adapter, profile(), perm)
    message = str(info.value)
    assert name in message and "no native sandbox" in message
    assert "allow_host_execution" in message and "isolation: container" in message


@pytest.mark.parametrize("name", NO_SANDBOX)
def test_write_without_native_sandbox_runs_with_host_opt_in(name):
    plan = resolve_launch(shipped(name), profile(allow_host=True), "workspace")
    assert plan.host_execution is True and plan.permission == "workspace"


@pytest.mark.parametrize("name", NATIVE)
def test_native_sandbox_adapters_accept_workspace_writes(name):
    adapter = shipped(name)
    assert adapter.sandbox.native is True
    plan = resolve_launch(adapter, profile(), "workspace")
    assert plan.host_execution is False


@pytest.mark.parametrize("name", SHIPPED)
def test_container_isolation_is_refused_until_implemented(name):
    with pytest.raises(Refused, match="container isolation not implemented yet"):
        resolve_launch(shipped(name), profile(isolation="container"), "read_only")


def test_permission_missing_from_profile_is_refused():
    with pytest.raises(Refused, match="no permission profile 'ghost'"):
        resolve_launch(shipped("claude"), profile(), "ghost")


def test_permission_missing_from_adapter_is_refused():
    with pytest.raises(Refused, match="adapter claude has no mapping for 'shell_only'"):
        resolve_launch(shipped("claude"), profile(), "shell_only")


def test_plan_env_merges_awg_off_and_permission_env():
    adapter = AdapterSpec.model_validate(adapter_data(
        permission_env={"read_only": {"FAKE_PERM": "ro"}}))
    plan = resolve_launch(adapter, profile(), "read_only")
    assert plan.env == {"FAKE_NO_AWG": "1", "FAKE_PERM": "ro"}


def test_plan_argv_uses_the_resolved_permission():
    adapter = AdapterSpec.model_validate(adapter_data())
    plan = resolve_launch(adapter, profile(), "read_only")
    argv = plan.argv(ArgvValues(prompt="hi", workspace="/w", permission="workspace"))
    assert argv == ["fake", "-p", "--read-only", "--no-mcp", "hi"]


def _with_shell_only(name: str) -> AdapterSpec:
    data = shipped(name).model_dump()
    data["permissions"]["shell_only"] = []
    return AdapterSpec.model_validate(data)
