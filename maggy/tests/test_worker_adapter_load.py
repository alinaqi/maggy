"""Adapter loader: shipped adapters and whole-file user overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.worker.adapter_loader import (
    AdapterConfigError, default_user_dir, load_adapter, load_adapters,
)
from worker_helpers import VALID_ADAPTER, adapter_data, write_adapter


def test_file_name_must_match_adapter_name(tmp_path):
    write_adapter(tmp_path / "shipped", VALID_ADAPTER, stem="other")
    with pytest.raises(AdapterConfigError, match="name"):
        load_adapters(tmp_path / "shipped", tmp_path / "user")


def test_user_override_replaces_shipped_adapter(tmp_path):
    write_adapter(tmp_path / "shipped", VALID_ADAPTER)
    write_adapter(tmp_path / "shipped", adapter_data(name="other"))
    override = {k: v for k, v in VALID_ADAPTER.items() if k != "disable_awg"}
    write_adapter(tmp_path / "user", {**override, "argv": ["mine", "{prompt}"]})
    adapters = load_adapters(tmp_path / "shipped", tmp_path / "user")
    assert adapters["fake"].argv == ["mine", "{prompt}"]
    assert adapters["fake"].disable_awg.flags == []
    assert adapters["other"].argv == VALID_ADAPTER["argv"]


def test_invalid_user_override_is_an_error(tmp_path):
    write_adapter(tmp_path / "shipped", VALID_ADAPTER)
    path = write_adapter(tmp_path / "user", adapter_data(output="nope"))
    with pytest.raises(AdapterConfigError, match=str(path)):
        load_adapter("fake", tmp_path / "shipped", tmp_path / "user")


def test_load_adapter_unknown_name(tmp_path):
    with pytest.raises(KeyError, match="ghost"):
        load_adapter("ghost", tmp_path / "shipped", tmp_path / "user")


def test_default_user_dir_is_under_maggy_home():
    assert default_user_dir() == Path.home() / ".maggy" / "adapters"


def test_shipped_adapters_load_cleanly():
    assert isinstance(load_adapters(user_dir=Path("/nonexistent")), dict)
