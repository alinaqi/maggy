"""Permission-bypass flags are rejected anywhere in an adapter (RFC §2.3, §2.6.7)."""

from __future__ import annotations

import pytest

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.bypass import bypass_flags
from maggy.worker.launch import Refused, resolve_launch
from worker_fixture_helpers import FIXTURES
from worker_helpers import adapter_data
from worker_launch_helpers import SHIPPED, profile, shipped

# Real bypass flags, each present in that CLI's recorded --help excerpt.
REAL = [("claude", "--dangerously-skip-permissions"),
        ("claude", "--allow-dangerously-skip-permissions"),
        ("claude", "bypassPermissions"),
        ("codex", "--dangerously-bypass-approvals-and-sandbox"),
        ("codex", "danger-full-access"),
        ("opencode", "--auto")]
FLAGS = [flag for _, flag in REAL] + ["--yolo", "--sandbox=danger-full-access",
                                      "--permission-mode=bypassPermissions"]


PLACES = {
    "argv": lambda d, f: d.update(argv=["fake", f, "{prompt}"]),
    "permissions": lambda d, f: d["permissions"].update(read_only=["--mode", f]),
    "model_flags": lambda d, f: d.update(model_flags=[f, "--model", "{model}"]),
    "disable_awg": lambda d, f: d["disable_awg"].update(flags=[f]),
    "env": lambda d, f: d["disable_awg"].update(env={"FAKE_MODE": f}),
}


def _placed(where: str, flag: str) -> AdapterSpec:
    data = adapter_data(sandbox={"native": True})
    PLACES[where](data, flag)
    return AdapterSpec.model_validate(data)


@pytest.mark.parametrize(("cli", "flag"), REAL)
def test_real_bypass_flags_are_documented_in_help(cli, flag):
    assert flag in (FIXTURES / cli / "help.txt").read_text()


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("where", sorted(PLACES))
def test_bypass_anywhere_is_refused_even_with_host_opt_in(where, flag):
    adapter = _placed(where, flag)
    assert bypass_flags(adapter)
    with pytest.raises(Refused, match="bypass") as info:
        resolve_launch(adapter, profile(allow_host=True), "read_only")
    assert "isolation: container" in str(info.value)


def test_bypass_with_container_isolation_still_refused_as_not_implemented():
    adapter = _placed("argv", "--yolo")
    with pytest.raises(Refused, match="container isolation not implemented yet"):
        resolve_launch(adapter, profile(isolation="container"), "read_only")


@pytest.mark.parametrize("name", SHIPPED)
def test_shipped_adapters_use_no_bypass_flags(name):
    assert bypass_flags(shipped(name)) == []


@pytest.mark.parametrize("safe", ["--auto-compact", "auto", "--permission-mode", "plan",
                                  "--sandbox", "workspace-write", "--yolo-mode-docs"])
def test_lookalikes_are_not_bypass_flags(safe):
    adapter = _placed("argv", safe)
    assert bypass_flags(adapter) == []
