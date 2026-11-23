"""Adapter permission_env: per-profile env, never overriding the AWG-off env."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from maggy.worker.adapter_spec import AdapterSpec
from worker_helpers import adapter_data


def test_permission_env_round_trips():
    data = adapter_data(permission_env={"workspace": {"FAKE_PERM": "rw"}})
    spec = AdapterSpec.model_validate(data)
    assert spec.permission_env == {"workspace": {"FAKE_PERM": "rw"}}


def test_permission_env_defaults_to_empty():
    assert AdapterSpec.model_validate(adapter_data()).permission_env == {}


def test_permission_env_for_unknown_profile_rejected():
    data = adapter_data(permission_env={"ghost": {"FAKE_PERM": "x"}})
    with pytest.raises(ValidationError, match="ghost"):
        AdapterSpec.model_validate(data)


def test_permission_env_cannot_override_awg_off_env():
    data = adapter_data(permission_env={"read_only": {"FAKE_NO_AWG": "0"}})
    with pytest.raises(ValidationError, match="FAKE_NO_AWG"):
        AdapterSpec.model_validate(data)
