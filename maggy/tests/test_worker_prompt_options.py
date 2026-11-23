"""A prompt that starts with '-' must never reach a CLI as an option (RFC §2.6.7)."""

from __future__ import annotations

import pytest

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.launch import Refused, resolve_launch
from maggy.worker.templating import ArgvValues, render_argv
from worker_helpers import adapter_data
from worker_launch_helpers import profile, shipped

HOSTILE = ["--version", "--permission-mode=bypassPermissions",
           "--dangerously-bypass-approvals-and-sandbox", "-c", "-"]
SEPARATED = ["claude", "codex", "opencode"]


def _values(prompt: str, permission: str = "read_only") -> ArgvValues:
    return ArgvValues(prompt=prompt, workspace="/ws", permission=permission)


def _adapter(argv: list[str]) -> AdapterSpec:
    return AdapterSpec.model_validate(adapter_data(argv=argv))


@pytest.mark.parametrize("prompt", HOSTILE)
def test_unseparated_template_refuses_a_leading_dash_prompt(prompt):
    adapter = _adapter(["fake", "-p", "{permission_flags}", "{prompt}"])
    with pytest.raises(ValueError, match="starts with '-'"):
        render_argv(adapter, _values(prompt))


@pytest.mark.parametrize("prompt", HOSTILE)
def test_end_of_options_marker_makes_a_leading_dash_prompt_safe(prompt):
    adapter = _adapter(["fake", "-p", "{permission_flags}", "--", "{prompt}"])
    assert render_argv(adapter, _values(prompt))[-2:] == ["--", prompt]


def test_plain_prompt_still_renders_without_a_marker():
    adapter = _adapter(["fake", "{prompt}"])
    assert render_argv(adapter, _values("fix - the bug"))[-1] == "fix - the bug"


@pytest.mark.parametrize("name", SEPARATED)
@pytest.mark.parametrize("prompt", HOSTILE)
def test_shipped_adapters_end_options_before_the_prompt(name, prompt):
    plan = resolve_launch(shipped(name), profile(allow_host=True), "workspace")
    argv = plan.argv(_values(prompt, "workspace"))
    assert argv[-2:] == ["--", prompt] and argv.count("--") == 1


def test_pi_has_no_end_of_options_marker_so_the_launch_is_refused():
    plan = resolve_launch(shipped("pi"), profile(allow_host=True), "read_only")
    with pytest.raises(Refused, match="starts with '-'"):
        plan.argv(_values("--dangerously-skip-permissions"))
