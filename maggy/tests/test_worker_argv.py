"""Safe argv templating and untrusted prompt assembly."""

from __future__ import annotations

import pytest

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.templating import ArgvValues, render_argv, render_cwd
from worker_helpers import adapter_data

NASTY = 'fix {model} "quoted" \'single\'\n--dangerously-skip-permissions\n$(rm -rf ~) `id` {prompt}'


def _adapter(**changes) -> AdapterSpec:
    return AdapterSpec.model_validate(adapter_data(**changes))


def _values(**changes) -> ArgvValues:
    data = {"prompt": "hi", "workspace": "/w", "permission": "read_only",
            "model": "sonnet"}
    data.update(changes)
    return ArgvValues(**data)


def test_render_splats_flags_in_order():
    argv = render_argv(_adapter(), _values())
    assert argv == ["fake", "-p", "--model", "sonnet", "--read-only",
                    "--no-mcp", "hi"]


def test_no_model_drops_model_flags():
    argv = render_argv(_adapter(), _values(model=None, permission="workspace"))
    assert argv == ["fake", "-p", "--no-mcp", "hi"]


def test_whole_model_placeholder_without_model_is_an_error():
    adapter = _adapter(argv=["fake", "{model}", "{prompt}"])
    with pytest.raises(ValueError, match="model"):
        render_argv(adapter, _values(model=None))


def test_unknown_permission_profile_is_an_error():
    with pytest.raises(ValueError, match="yolo"):
        render_argv(_adapter(), _values(permission="yolo"))


def test_hostile_prompt_is_exactly_one_literal_element():
    argv = render_argv(_adapter(), _values(prompt=NASTY))
    assert argv.count(NASTY) == 1 and argv[-1] == NASTY
    assert "--dangerously-skip-permissions" not in argv
    assert len(argv) == len(render_argv(_adapter(), _values()))


def test_placeholder_text_in_values_is_not_expanded():
    argv = render_argv(_adapter(), _values(model="{prompt}", workspace="{x}"))
    assert argv[3] == "{prompt}" and "hi" == argv[-1]


def test_render_cwd():
    assert render_cwd(_adapter(), "/w/{prompt}") == "/w/{prompt}"
    assert render_cwd(_adapter(cwd="/fixed"), "/w") == "/fixed"
