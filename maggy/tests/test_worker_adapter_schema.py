"""Adapter YAML schema: bad files fail with the file and key path."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.worker.adapter_loader import (
    AdapterConfigError, load_adapters,
)
from maggy.worker.adapter_spec import AdapterSpec
from worker_helpers import VALID_ADAPTER, adapter_data, write_adapter


def _load_bad(tmp_path: Path, data: dict) -> str:
    path = write_adapter(tmp_path / "shipped", data)
    with pytest.raises(AdapterConfigError) as info:
        load_adapters(tmp_path / "shipped", tmp_path / "user")
    message = str(info.value)
    assert str(path) in message
    return message


def test_valid_adapter_round_trips():
    spec = AdapterSpec.model_validate(VALID_ADAPTER)
    assert spec.output == "text" and spec.sandbox.native is False
    assert spec.cost.fixed_reservation_usd == 0.5
    assert spec.disable_awg.env == {"FAKE_NO_AWG": "1"}
    assert AdapterSpec.model_validate(spec.model_dump()) == spec


def test_unknown_key_rejected_with_file_and_key(tmp_path):
    message = _load_bad(tmp_path, adapter_data(sandbox={"native": True, "bogus": 1}))
    assert "sandbox.bogus" in message


def test_embedded_placeholder_rejected(tmp_path):
    data = adapter_data(argv=["fake", "--prompt={prompt}"])
    message = _load_bad(tmp_path, data)
    assert "argv" in message and "embedded" in message


def test_unknown_placeholder_rejected(tmp_path):
    data = adapter_data(argv=["fake", "{secret_flags}", "{prompt}"])
    message = _load_bad(tmp_path, data)
    assert "argv" in message and "{secret_flags}" in message


def test_unknown_parser_rejected(tmp_path):
    message = _load_bad(tmp_path, adapter_data(output="xml"))
    assert "output" in message


@pytest.mark.parametrize("argv", [["fake"], ["fake", "{prompt}", "{prompt}"]])
def test_prompt_must_appear_exactly_once(tmp_path, argv):
    assert "argv" in _load_bad(tmp_path, adapter_data(argv=argv))


def test_placeholders_not_allowed_in_permission_flags(tmp_path):
    data = adapter_data(permissions={"workspace": ["{prompt}"]})
    assert "permissions.workspace" in _load_bad(tmp_path, data)


def test_cwd_only_accepts_whole_workspace_placeholder(tmp_path):
    assert "cwd" in _load_bad(tmp_path, adapter_data(cwd="/x/{workspace}"))
